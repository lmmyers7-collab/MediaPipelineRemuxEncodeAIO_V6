"""Media-policy and publish Basic-page settings metadata."""

from __future__ import annotations

from ..metadata_choices import CONFIG_LIST_CHOICES
from ..metadata_support import (
    AUDIO_DOWNMIX_MODE_DESCRIPTIONS,
    AUDIO_MAX_CHANNEL_DESCRIPTIONS,
    AUDIO_TRANSCODE_CODEC_DESCRIPTIONS,
)
from .policy import (
    AUDIO_PASSTHROUGH_PROFILE_DEFAULT,
    AUDIO_PASSTHROUGH_PROFILE_DESCRIPTIONS,
    AUDIO_PASSTHROUGH_PROFILE_NAMES,
)

PREFERRED_DEFAULT_AUDIO_LANGUAGE_CHOICES = tuple(
    value for value, _label in CONFIG_LIST_CHOICES["PreferredDefaultAudioLanguages"]
)
PREFERRED_DEFAULT_AUDIO_LANGUAGE_CHOICE_HELP = dict(
    CONFIG_LIST_CHOICES["PreferredDefaultAudioLanguages"]
)

BASIC_FINAL_LIBRARY_PROMOTION_FIELDS = (
{
        "page": "Basic",
        "section": "Final Library Promotion",
        "key": "FinalLibraryPromotionEnabled",
        "label": "Enable Promotion",
        "kind": "bool",
        "default": False,
        "help": "Expose the manual Promote Queue to Final Library workflow for completed publish output.",
    },
{
        "page": "Basic",
        "section": "Final Library Promotion",
        "key": "FinalLibraryPromotionRules",
        "label": "Source to Destination Rules",
        "kind": "string",
        "default": "[]",
        "help": "JSON array of rules with label, enabled, source_root, and destination_root. The longest matching source_root wins.",
    },
{
        "page": "Basic",
        "section": "Final Library Promotion",
        "key": "FinalLibraryPromotionVerificationMode",
        "label": "Verification Mode",
        "kind": "combo",
        "choices": ("cautious", "fast"),
        "default": "cautious",
        "help": "Cautious verifies byte size and SHA-256 hashes. Fast verifies destination existence and byte size only.",
    },
{
        "page": "Basic",
        "section": "Final Library Promotion",
        "key": "FinalLibraryPromotionCleanupAfterVerified",
        "label": "Cleanup After Verified",
        "kind": "bool",
        "default": False,
        "help": "After verified promotion, delete only copied publish-output files and remove empty folders below Outsource.",
    },
{
        "page": "Basic",
        "section": "Final Library Promotion",
        "key": "FinalLibraryPromotionOverwriteExisting",
        "label": "Overwrite Existing Final Files",
        "kind": "bool",
        "default": False,
        "help": "Destructive: delete the existing final file immediately before copying the replacement.",
    },
)

BASIC_AUDIO_FIELDS = (
{
        "page": "Basic",
        "section": "Audio",
        "key": "AudioPassthroughProfile",
        "label": "Audio Passthrough Profile",
        "kind": "combo",
        "choices": AUDIO_PASSTHROUGH_PROFILE_NAMES,
        "default": AUDIO_PASSTHROUGH_PROFILE_DEFAULT,
        "choice_help": AUDIO_PASSTHROUGH_PROFILE_DESCRIPTIONS,
        "help": "Structured policy for which audio codecs can be copied. Use custom_codec_list only when you need manual codec control.",
    },
{
        "page": "Basic",
        "section": "Audio",
        "key": "CompatibleAudioCodecs",
        "label": "Custom Audio Passthrough Codecs",
        "kind": "list",
        "help": "Manual codecs copied only when Audio Passthrough Profile is custom_codec_list. Structured profiles populate this list on save.",
    },
{
        "page": "Basic",
        "section": "Audio",
        "key": "PreferredDefaultAudioLanguages",
        "label": "Primary Default Audio Language",
        "kind": "list",
        "choices": PREFERRED_DEFAULT_AUDIO_LANGUAGE_CHOICES,
        "choice_help": PREFERRED_DEFAULT_AUDIO_LANGUAGE_CHOICE_HELP,
        "help": "Primary default-audio language preference. If the selected language is not present, the highest-fidelity non-commentary track is chosen.",
    },
{
        "page": "Basic",
        "section": "Audio",
        "key": "AudioTranscodeCodec",
        "label": "Transcode Codec",
        "kind": "combo",
        "choices": ("eac3", "ac3", "aac"),
        "default": "eac3",
        "choice_help": AUDIO_TRANSCODE_CODEC_DESCRIPTIONS,
        "help": "Codec used when an audio track must be normalized instead of copied.",
    },
{
        "page": "Basic",
        "section": "Audio",
        "key": "AudioTranscodeBitrate",
        "label": "Transcode Bitrate",
        "kind": "combo",
        "choices": ("384k", "448k", "640k", "768k"),
        "default": "640k",
        "help": "Bitrate used for normalized audio tracks. Ignored when 'Auto Bitrate by Channels' is on.",
    },
{
        "page": "Basic",
        "section": "Audio",
        "key": "AudioTranscodeAutoBitrateByChannels",
        "label": "Auto Bitrate by Channels",
        "kind": "bool",
        "default": False,
        "help": "When on, audio transcode bitrate is picked from a codec/channel-count table (e.g. 192k for 2.0 EAC3, 448k for 5.1 EAC3, 640k for 7.1 EAC3) instead of the static 'Transcode Bitrate' value. Saves space on commentary / stereo tracks; gives 7.1 mixes more bit pool.",
    },
{
        "page": "Basic",
        "section": "Audio",
        "key": "AudioDownmixMode",
        "label": "Downmix Mode",
        "kind": "combo",
        "choices": ("max_channels", "preserve", "stereo"),
        "default": "max_channels",
        "choice_help": AUDIO_DOWNMIX_MODE_DESCRIPTIONS,
        "help": "Controls channel count when audio is transcoded: cap to the maximum, preserve source channels, or force stereo.",
    },
{
        "page": "Basic",
        "section": "Audio",
        "key": "AudioMaxChannels",
        "label": "Max Channels",
        "kind": "combo_int",
        "choices": ("2", "6", "8"),
        "default": 6,
        "choice_help": AUDIO_MAX_CHANNEL_DESCRIPTIONS,
        "help": "Maximum channels for transcodes when Downmix Mode is max_channels.",
    },
{
        "page": "Basic",
        "section": "Audio",
        "key": "AllowNoAudio",
        "label": "Allow No-Audio Outputs",
        "kind": "bool",
        "default": False,
        "help": "Permit silent source files to be processed without audio. Leave off for normal Plex media.",
    },
)

BASIC_PENDING_PUBLISH_FIELDS = (
{
        "page": "Basic",
        "section": "Routing",
        "key": "DeferredPublish",
        "label": "Deferred Publish",
        "kind": "bool",
        "help": "Park completed outputs locally instead of uploading them immediately. Use the recovery action to publish parked outputs later.",
    },
{
        "page": "Basic",
        "section": "Routing",
        "key": "PendingPublishDrainMode",
        "label": "Pending Publish Drain Mode",
        "kind": "combo",
        "choices": ("manual", "trusted"),
        "default": "manual",
        "help": "manual keeps deferred publish parked until operator action. trusted permits unattended backend-owned drain only for manifests that pass existing trust validation.",
    },
{
        "page": "Basic",
        "section": "Routing",
        "key": "PendingPublishDrainBatchSize",
        "label": "Pending Publish Drain Batch Size",
        "kind": "int",
        "default": 100,
        "help": "Maximum pending-publish manifests considered per normal or trusted deferred drain pass.",
    },
)
