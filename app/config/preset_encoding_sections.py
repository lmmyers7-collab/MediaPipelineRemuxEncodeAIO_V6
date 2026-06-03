"""HandBrake-style preset section models."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ResolutionLimit = Literal["source", "480p", "720p", "1080p", "2160p", "custom"]
ScalingPolicy = Literal["never_upscale", "allow_upscale", "preserve_source"]
FilterStrength = Literal["off", "low", "medium", "high", "custom"]
TargetMode = Literal["auto", "constant_quality", "average_bitrate", "max_bitrate"]


def _normalized_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalized_lower(value: Any) -> str:
    return _normalized_text(value).lower()


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


class PresetSectionModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", populate_by_name=True)


class DimensionsPolicy(PresetSectionModel):
    resolution_limit: ResolutionLimit = Field(default="source", alias="resolutionLimit")
    custom_max_height: int | None = Field(default=None, ge=1, alias="customMaxHeight")
    scaling_policy: ScalingPolicy = Field(default="never_upscale", alias="scalingPolicy")
    aspect_policy: Literal["preserve_display_aspect", "custom"] = Field(default="preserve_display_aspect", alias="aspectPolicy")
    crop_mode: Literal["off", "auto", "custom"] = Field(default="off", alias="cropMode")
    pixel_aspect_mode: Literal["source", "auto", "custom"] = Field(default="source", alias="pixelAspectMode")
    max_direct_copy_height: int = Field(default=2160, ge=0, alias="maxDirectCopyHeight")
    h264_direct_copy_max_height: int = Field(default=1080, ge=0, alias="h264DirectCopyMaxHeight")
    scale_mode: Literal["source", "downscale_only", "custom"] = Field(default="source", alias="scaleMode")

    @field_validator("resolution_limit", "scaling_policy", "aspect_policy", "crop_mode", "pixel_aspect_mode", "scale_mode", mode="before")
    @classmethod
    def _normalize_dimensions_choice(cls, value: Any) -> str:
        return _normalized_lower(value)

    @model_validator(mode="after")
    def _validate_custom_limit(self) -> DimensionsPolicy:
        if self.resolution_limit == "custom" and not self.custom_max_height:
            raise ValueError("Dimensions: custom resolution limit requires customMaxHeight.")
        return self


class FiltersPolicy(PresetSectionModel):
    detelecine: Literal["off", "auto", "custom"] = "off"
    deinterlace: Literal["off", "auto", "decomb", "yadif", "custom"] = "off"
    denoise: FilterStrength = "off"
    sharpen: FilterStrength = "off"
    deblock: FilterStrength = "off"
    chroma_smooth: FilterStrength = Field(default="off", alias="chromaSmooth")
    colorspace: Literal["source", "bt709", "bt2020", "custom"] = "source"
    strip_ass_formatting: bool = Field(default=True, alias="stripAssFormatting")
    remove_karaoke: bool = Field(default=True, alias="removeKaraoke")
    merge_adjacent: bool = Field(default=True, alias="mergeAdjacent")
    merge_threshold_ms: int = Field(default=150, ge=0, alias="mergeThresholdMs")

    @field_validator("detelecine", "deinterlace", "denoise", "sharpen", "deblock", "chroma_smooth", "colorspace", mode="before")
    @classmethod
    def _normalize_filter_choice(cls, value: Any) -> str:
        return _normalized_lower(value)


class VideoPolicy(PresetSectionModel):
    codec: str = Field(default="hevc_nvenc", min_length=1)
    codec_family: Literal["h264", "h265", "hevc", "av1", "copy"] = Field(default="hevc", alias="codecFamily")
    encoder_backend: Literal["auto", "nvenc", "x264", "x265", "qsv", "svt_av1", "copy"] = Field(default="nvenc", alias="encoderBackend")
    encoder_speed_preset: str = Field(default="p7", min_length=1, alias="encoderSpeedPreset")
    quality_target: int = Field(default=22, ge=0, alias="qualityTarget")
    target_mode: TargetMode = Field(default="auto", alias="targetMode")
    target_bitrate_mbps: float | None = Field(default=None, gt=0, alias="targetBitrateMbps")
    max_bitrate_mbps: float | None = Field(default=None, gt=0, alias="maxBitrateMbps")
    framerate_mode: Literal["same_as_source", "constant", "variable"] = Field(default="same_as_source", alias="framerateMode")
    profile: str = ""
    level: str = ""
    tune: str = ""
    encoder_quality_preset: Literal["balanced_nvenc", "quality_nvenc", "fast_nvenc", "compatibility", "custom_legacy_flags"] = Field(default="balanced_nvenc", alias="encoderQualityPreset")
    target_selection: Literal["auto", "tv_balanced", "tv_space_saver", "movie_balanced", "movie_archive", "plex_compat"] = Field(default="auto", alias="targetSelection")

    @field_validator("codec", "encoder_speed_preset", mode="before")
    @classmethod
    def _strip_text_choice(cls, value: Any) -> str:
        return _normalized_text(value)

    @field_validator("codec_family", "encoder_backend", "target_mode", "framerate_mode", "encoder_quality_preset", "target_selection", mode="before")
    @classmethod
    def _normalize_video_choice(cls, value: Any) -> str:
        return _normalized_lower(value)

    @model_validator(mode="after")
    def _validate_target_mode(self) -> VideoPolicy:
        if self.target_mode == "average_bitrate" and self.target_bitrate_mbps is None:
            raise ValueError("Video: average bitrate mode requires targetBitrateMbps.")
        if self.target_mode == "max_bitrate" and self.max_bitrate_mbps is None:
            raise ValueError("Video: max bitrate mode requires maxBitrateMbps.")
        return self


class AudioPolicy(PresetSectionModel):
    passthrough_default: bool = Field(default=True, alias="passthroughDefault")
    passthrough_profile: Literal["plex_balanced", "compatibility", "lossless_passthrough", "custom_codec_list"] = Field(default="plex_balanced", alias="passthroughProfile")
    compatible_codecs: list[str] = Field(default_factory=lambda: ["aac", "ac3", "eac3", "mp3", "opus", "vorbis", "truehd", "mlp"], alias="compatibleCodecs")
    preferred_default_languages: list[str] = Field(default_factory=lambda: ["english"], alias="preferredDefaultLanguages")
    transcode_codec: Literal["eac3", "ac3", "aac"] = Field(default="eac3", alias="transcodeCodec")
    transcode_bitrate: str = Field(default="640k", pattern=r"^[1-9]\d*k$", alias="transcodeBitrate")
    transcode_auto_bitrate_by_channels: bool = Field(default=False, alias="transcodeAutoBitrateByChannels")
    downmix_mode: Literal["preserve", "max_channels", "stereo"] = Field(default="max_channels", alias="downmixMode")
    max_channels: int = Field(default=6, ge=1, le=16, alias="maxChannels")
    force_transcode: bool = Field(default=False, alias="forceTranscode")
    allow_no_audio: bool = Field(default=False, alias="allowNoAudio")
    mp4_copy_codecs: list[str] = Field(default_factory=lambda: ["aac", "ac3", "eac3", "mp3", "alac"], alias="mp4CopyCodecs")

    @field_validator("passthrough_profile", "transcode_codec", "downmix_mode", mode="before")
    @classmethod
    def _normalize_audio_choice(cls, value: Any) -> str:
        return _normalized_lower(value)

    @field_validator("compatible_codecs", "preferred_default_languages", "mp4_copy_codecs", mode="before")
    @classmethod
    def _coerce_audio_list(cls, value: Any) -> list[str]:
        return [item.lower() for item in _normalized_list(value)]


class SubtitlePolicy(PresetSectionModel):
    mode: Literal["keep", "drop", "convert_preferred", "burn_forced"] = "keep"
    keep_languages: list[str] = Field(default_factory=lambda: ["eng", "en", "und", ""], alias="keepLanguages")
    generate_preferred_srt: bool = Field(default=True, alias="generatePreferredSrt")
    burn_in_forced: bool = Field(default=False, alias="burnInForced")
    language_filter_mode: Literal["off", "keep_configured", "drop_unconfigured"] = Field(default="keep_configured", alias="languageFilterMode")
    convert_tx3g_to_srt: bool = Field(default=True, alias="convertTx3gToSrt")
    drop_tx3g_after_conversion: bool = Field(default=False, alias="dropTx3gAfterConversion")
    create_external_tx3g_srt_sidecars: bool = Field(default=False, alias="createExternalTx3gSrtSidecars")
    tx3g_extract_languages: list[str] = Field(default_factory=lambda: ["eng", "en", "und"], alias="tx3gExtractLanguages")
    tx3g_preserve_existing_srt: bool = Field(default=True, alias="tx3gPreserveExistingSrt")
    tx3g_treat_forced_as_separate: bool = Field(default=True, alias="tx3gTreatForcedAsSeparate")
    convert_bdpgs_to_srt: bool = Field(default=False, alias="convertBdpgsToSrt")
    drop_bdpgs_after_conversion: bool = Field(default=False, alias="dropBdpgsAfterConversion")
    bdpgs_extract_languages: list[str] = Field(default_factory=lambda: ["eng", "en", "und"], alias="bdpgsExtractLanguages")
    bdpgs_ocr_tool_path: str = Field(default=r"Tools\PgsToSrt\PgsToSrt.exe", alias="bdpgsOcrToolPath")
    bdpgs_ocr_tessdata_path: str = Field(default=r"Tools\PgsToSrt\tessdata", alias="bdpgsOcrTessdataPath")
    convert_vobsub_to_srt: bool = Field(default=False, alias="convertVobSubToSrt")
    drop_vobsub_after_conversion: bool = Field(default=False, alias="dropVobSubAfterConversion")
    vobsub_extract_languages: list[str] = Field(default_factory=lambda: ["eng", "en", "und"], alias="vobSubExtractLanguages")
    vobsub_ocr_tool_path: str = Field(default=r"Tools\SubtitleEditLegacy\SubtitleEdit.exe", alias="vobSubOcrToolPath")
    drop_ass_after_conversion: bool = Field(default=False, alias="dropAssAfterConversion")
    keep_signs_and_songs: bool = Field(default=True, alias="keepSignsAndSongs")
    treat_ass_signs_songs_as_forced: bool = Field(default=False, alias="treatAssSignsSongsAsForced")
    treat_tx3g_signs_songs_as_forced: bool = Field(default=False, alias="treatTx3gSignsSongsAsForced")
    treat_bdpgs_signs_songs_as_forced: bool = Field(default=False, alias="treatBdpgsSignsSongsAsForced")
    treat_vobsub_signs_songs_as_forced: bool = Field(default=False, alias="treatVobSubSignsSongsAsForced")
    sdh_title_keywords: list[str] = Field(default_factory=list, alias="sdhTitleKeywords")
    supplemental_keywords: list[str] = Field(default_factory=list, alias="supplementalKeywords")
    excluded_styles: list[str] = Field(default_factory=list, alias="excludedStyles")
    included_styles: list[str] = Field(default_factory=list, alias="includedStyles")
    mp4_copy_codecs: list[str] = Field(default_factory=lambda: ["mov_text", "tx3g"], alias="mp4CopyCodecs")

    @field_validator("mode", "language_filter_mode", mode="before")
    @classmethod
    def _normalize_subtitle_choice(cls, value: Any) -> str:
        return _normalized_lower(value)

    @field_validator("keep_languages", "tx3g_extract_languages", "bdpgs_extract_languages", "vobsub_extract_languages", "sdh_title_keywords", "supplemental_keywords", "excluded_styles", "included_styles", "mp4_copy_codecs", mode="before")
    @classmethod
    def _coerce_subtitle_list(cls, value: Any) -> list[str]:
        return _normalized_list(value)

    @model_validator(mode="after")
    def _validate_subtitle_policy(self) -> SubtitlePolicy:
        if not self.convert_tx3g_to_srt and self.drop_tx3g_after_conversion:
            raise ValueError("Subtitles: Drop TX3G after conversion requires TX3G to SRT conversion.")
        if not self.convert_tx3g_to_srt and self.create_external_tx3g_srt_sidecars:
            raise ValueError("Subtitles: External TX3G SRT sidecars require TX3G to SRT conversion.")
        if not self.convert_bdpgs_to_srt and self.drop_bdpgs_after_conversion:
            raise ValueError("Subtitles: Drop BDPGS after OCR requires BDPGS OCR to SRT conversion.")
        if self.convert_bdpgs_to_srt and not self.bdpgs_ocr_tool_path.strip():
            raise ValueError("Subtitles: BDPGS OCR requires a BDPGS OCR tool path.")
        if not self.convert_vobsub_to_srt and self.drop_vobsub_after_conversion:
            raise ValueError("Subtitles: Drop VobSub after OCR requires VobSub OCR to SRT conversion.")
        if self.convert_vobsub_to_srt and not self.vobsub_ocr_tool_path.strip():
            raise ValueError("Subtitles: VobSub OCR requires a VobSub OCR tool path.")
        return self


class ContainerPolicy(PresetSectionModel):
    format: Literal["mkv", "mp4"] = "mkv"
    force_remux: bool = Field(default=True, alias="forceRemux")
    remux_when_possible: bool = Field(default=True, alias="remuxWhenPossible")
    mp4_requires_compatible_streams: bool = Field(default=True, alias="mp4RequiresCompatibleStreams")

    @field_validator("format", mode="before")
    @classmethod
    def _normalize_format(cls, value: Any) -> str:
        return _normalized_lower(value)


__all__ = [
    "AudioPolicy",
    "ContainerPolicy",
    "DimensionsPolicy",
    "FiltersPolicy",
    "SubtitlePolicy",
    "VideoPolicy",
]
