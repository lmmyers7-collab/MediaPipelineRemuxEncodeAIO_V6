"""Preset key compatibility and migration status metadata."""

from __future__ import annotations

from typing import Literal

from mediapipeline.contracts.config import Config

MigrationStatus = Literal[
    "stable_persisted_key",
    "label_only_rename",
    "legacy_alias_accepted",
    "deprecated_warn_only",
    "accepted_one_release",
    "accepted_forever",
    "blocked_future_key",
    "migration_deferred",
]

MIGRATION_STATUS_VALUES: tuple[MigrationStatus, ...] = (
    "stable_persisted_key",
    "label_only_rename",
    "legacy_alias_accepted",
    "deprecated_warn_only",
    "accepted_one_release",
    "accepted_forever",
    "blocked_future_key",
    "migration_deferred",
)

LABEL_ONLY_RENAMES: dict[str, str] = {
    "RoutingProfile": "Library goal",
    "RouteThresholdMode": "What forces an encode?",
    "SizeGuardMode": "If encoded output is too large",
    "EncodeTuningPreset": "NVENC tuning bundle",
    "EncodeLadder": "How encode targets are calculated",
    "MaxEncodeGrowthPercent": "Quality-encode size tolerance",
    "CompatibilityEncodeGrowthPercent": "Compatibility-encode size tolerance",
    "MovieRoute1080pTargetSizeGB": "Movie 1080p target output size",
    "MovieRoute1440pTargetSizeGB": "Movie 1440p target output size",
    "MovieRoute4KTargetSizeGB": "Movie 4K target output size",
    "TVRoute1080pTargetSizeGB": "TV 1080p target output size",
    "TVRoute1440pTargetSizeGB": "TV 1440p target output size",
    "TVRoute4KTargetSizeGB": "TV 4K target output size",
    "Route1080pUpperHeightTolerancePercent": "1080p upper height tolerance",
    "Route1080pMaxVideoBitrateMbps": "1080p max bitrate for direct copy",
    "Route1440pLowerHeightTolerancePercent": "1440p lower height tolerance",
    "Route1440pUpperHeightTolerancePercent": "1440p upper height tolerance",
    "Route1440pMaxVideoBitrateMbps": "1440p max bitrate for direct copy",
    "Route4KLowerHeightTolerancePercent": "4K lower height tolerance",
    "Route4KMaxVideoBitrateMbps": "4K max bitrate for direct copy",
    "VideoPreset": "Encoder Speed Preset",
    "ExtraVideoFlags": "Advanced Encoder Flags",
    "RemuxSafeVideoCodecs": "Direct Copy Video Codec Allowlist",
}

FRIENDLY_LABEL_PERSISTED_KEY_ALIASES: dict[str, str] = {
    "LibraryGoal": "RoutingProfile",
    "Library goal": "RoutingProfile",
    "ProcessingStrategy": "RoutingProfile",
    "Processing Strategy": "RoutingProfile",
    "WhatForcesAnEncode": "RouteThresholdMode",
    "What forces an encode?": "RouteThresholdMode",
    "EnforcementMode": "RouteThresholdMode",
    "Enforcement Mode": "RouteThresholdMode",
    "IfEncodedOutputIsTooLarge": "SizeGuardMode",
    "If encoded output is too large": "SizeGuardMode",
    "OutputSizeCheck": "SizeGuardMode",
    "Output Size Check": "SizeGuardMode",
    "NVENCTuningBundle": "EncodeTuningPreset",
    "NVENC tuning bundle": "EncodeTuningPreset",
    "EncoderQualityPreset": "EncodeTuningPreset",
    "Encoder Quality Preset": "EncodeTuningPreset",
    "HowEncodeTargetsAreCalculated": "EncodeLadder",
    "How encode targets are calculated": "EncodeLadder",
    "EncodeTargetMode": "EncodeLadder",
    "Encode Target Mode": "EncodeLadder",
    "QualityEncodeSizeTolerance": "MaxEncodeGrowthPercent",
    "Quality-encode size tolerance": "MaxEncodeGrowthPercent",
    "CompatibilityEncodeSizeTolerance": "CompatibilityEncodeGrowthPercent",
    "Compatibility-encode size tolerance": "CompatibilityEncodeGrowthPercent",
    "Movie1080pTargetOutputSize": "MovieRoute1080pTargetSizeGB",
    "Movie 1080p target output size": "MovieRoute1080pTargetSizeGB",
    "Movie1440pTargetOutputSize": "MovieRoute1440pTargetSizeGB",
    "Movie 1440p target output size": "MovieRoute1440pTargetSizeGB",
    "Movie4KTargetOutputSize": "MovieRoute4KTargetSizeGB",
    "Movie 4K target output size": "MovieRoute4KTargetSizeGB",
    "TV1080pTargetOutputSize": "TVRoute1080pTargetSizeGB",
    "TV 1080p target output size": "TVRoute1080pTargetSizeGB",
    "TV1440pTargetOutputSize": "TVRoute1440pTargetSizeGB",
    "TV 1440p target output size": "TVRoute1440pTargetSizeGB",
    "TV4KTargetOutputSize": "TVRoute4KTargetSizeGB",
    "TV 4K target output size": "TVRoute4KTargetSizeGB",
    "1080pUpperHeightTolerance": "Route1080pUpperHeightTolerancePercent",
    "1080p upper height tolerance": "Route1080pUpperHeightTolerancePercent",
    "1080ishMaxBitrateForDirectCopy": "Route1080pMaxVideoBitrateMbps",
    "1080-ish max bitrate for direct copy": "Route1080pMaxVideoBitrateMbps",
    "1080pMaxBitrateForDirectCopy": "Route1080pMaxVideoBitrateMbps",
    "1080p max bitrate for direct copy": "Route1080pMaxVideoBitrateMbps",
    "1440pLowerHeightTolerance": "Route1440pLowerHeightTolerancePercent",
    "1440p lower height tolerance": "Route1440pLowerHeightTolerancePercent",
    "1440pUpperHeightTolerance": "Route1440pUpperHeightTolerancePercent",
    "1440p upper height tolerance": "Route1440pUpperHeightTolerancePercent",
    "1440pMaxBitrateForDirectCopy": "Route1440pMaxVideoBitrateMbps",
    "1440p max bitrate for direct copy": "Route1440pMaxVideoBitrateMbps",
    "4KLowerHeightTolerance": "Route4KLowerHeightTolerancePercent",
    "4K lower height tolerance": "Route4KLowerHeightTolerancePercent",
    "4KMaxBitrateForDirectCopy": "Route4KMaxVideoBitrateMbps",
    "4K max bitrate for direct copy": "Route4KMaxVideoBitrateMbps",
    "EncoderSpeedPreset": "VideoPreset",
    "Encoder Speed Preset": "VideoPreset",
    "AdvancedEncoderFlags": "ExtraVideoFlags",
    "Advanced Encoder Flags": "ExtraVideoFlags",
    "DirectCopyVideoCodecAllowlist": "RemuxSafeVideoCodecs",
    "Direct Copy Video Codec Allowlist": "RemuxSafeVideoCodecs",
}

PERSISTED_KEY_MIGRATION_STATUS: dict[str, MigrationStatus] = {
    key: "stable_persisted_key"
    for key in Config.model_fields
}

LEGACY_COMPATIBILITY_KEY_STATUSES: dict[str, MigrationStatus] = {
    "SourceMovies": "accepted_forever",
    "SourceTV": "accepted_forever",
    "Outsource": "accepted_forever",
    "LibraryProfiles": "accepted_forever",
    "FinalLibraryPromotionRules": "accepted_forever",
    "editor_overrides": "legacy_alias_accepted",
    "media_overrides": "legacy_alias_accepted",
}

BLOCKED_FUTURE_PERSISTED_KEYS: dict[str, MigrationStatus] = {
    alias: "blocked_future_key"
    for alias in FRIENDLY_LABEL_PERSISTED_KEY_ALIASES
}

LABEL_ONLY_RENAME_POLICIES: tuple[dict[str, object], ...] = tuple(
    {
        "persisted_key": key,
        "display_label": label,
        "status": "label_only_rename",
        "accepted_as_persisted_key": False,
    }
    for key, label in LABEL_ONLY_RENAMES.items()
)
