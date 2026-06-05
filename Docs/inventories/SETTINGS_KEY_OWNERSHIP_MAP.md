# Settings Key Ownership Map

Date: 2026-06-03

Maps the highest-impact configuration keys to: builder page/group, mutation risk, Settings-to-Launch handoff visibility, and test coverage. Source: `config_schema.py`, `settings_risk_policy_rules.py`, `docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md`.

134 backend metadata keys are present in `CONFIG_FIELD_DEFINITIONS`. 122 are covered by structured WebView builder arrays, `LibraryProfiles` is handled by the dedicated Library Profiles editor, 9 non-secret keys are known advanced/direct-config metadata without routine builders, and 2 intentionally hidden auth keys remain excluded. This document covers the highest-impact subset plus all hidden keys.

---

## Risk Tier Definitions

| Risk tier | Meaning |
|---|---|
| **Critical** | Misconfiguration can cause data loss, overwrite source files, or create silent processing failures with no warning |
| **High** | Misconfiguration causes incorrect output, wrong route decisions, failed encodes, or auth failures |
| **Medium** | Misconfiguration degrades performance, causes unexpected behavior, or requires operator investigation |
| **Low** | Misconfiguration affects display, logging verbosity, or non-essential behavior |

---

## Intentionally Hidden Auth Keys

These keys have no structured WebView builder panel because they are auth secrets. They must be set by direct PSD1 edit or a dedicated future secret-handling design that prevents browser exposure.

| Key | Category | Risk | Reason hidden | Launch handoff | Tests |
|---|---|---|---|---|---|
| `CoordinatorAuthToken` | Network / Auth | **Critical** | Auth secret — must never appear in WebView builder, browser storage, or JS heap | Not surfaced | Excluded from WebView by design |
| `WorkerAuthToken` | Network / Auth | **Critical** | Auth secret — must match coordinator | Not surfaced | Excluded from WebView by design |

---

## High-Impact Structured Keys

### Paths Group (File Safety / Publish builder)

| Key | Risk | Description | Launch handoff | Tests |
|---|---|---|---|---|
| `SourceMovies` | **Critical** | Source folder for movies. Wrong path → no movies discovered. | Yes — path readiness row | `test_service_config_path_warnings.py` |
| `SourceTV` | **Critical** | Source folder for TV series. Wrong path → no TV discovered. | Yes — path readiness row | `test_service_config_path_warnings.py` |
| `Outsource` | **Critical** | Final output destination. Wrong path → outputs go to wrong location or fail. | Yes — output path readiness | `test_service_config_path_warnings.py` |
| `LocalBase` | **Critical** | Scratch disk (LocalBase / working directory). Wrong path → pipeline fails to start. | Yes — scratch disk readiness | `test_service_config_path_warnings.py` |
| `DeferredPublish` | **High** | When `true`, outputs are parked in `PendingServerPush` rather than moved immediately. Changing while parked outputs exist can cause drain confusion. | Yes — deferred publish policy visible in Launch handoff | `test_facade_pending_publish_policy.py`, `test_service_pending_publish_manifest.py` |
| `MinFreeSpaceGB` | **High** | Scratch disk free-space reserve (default 50 GB). Setting too low allows scratch to fill. | Yes — preflight safety row | `test_settings_risk_policy_rules.py` |
| `OutsourceMinFreeSpaceGB` | **High** | Output destination free-space reserve. Setting too low allows destination to fill. | Yes — preflight safety row | `test_settings_risk_policy_rules.py` |
| `EnableIntegrityCheck` | Medium | Pre-process media verification. Disabling speeds up processing but skips source file integrity probe. | Yes — integrity posture row | `test_service_config_validation.py` |
| `CreateTVSubfolder` | Low | Creates `Show/Season XX/` subfolder structure (Plex style). Affects output path layout. | Not directly surfaced | `test_service_config_value_checks.py` |

### Routing / Size Group

| Key | Risk | Description | Launch handoff | Tests |
|---|---|---|---|---|
| `RoutingProfile` | **High** | High-level policy: `plex_direct_stream`, `plex_direct_play`, `archive_shrink`, `archive_quality`, `manual`. Drives all route decisions. | Yes — active route policy row | `test_service_config_profiles.py`, `test_service_config_validation.py` |
| `RouteThresholdMode` | **High** | Selects whether initial routing treats size, bitrate, or both as hard thresholds. Default preserves compatibility-advisory behavior. | Yes — active route policy row | `test_service_config_option_policy.py`, `test_stage_entrypoint.py` |
| `VideoCodec` | **High** | Encoder: `hevc_nvenc`, `libx265`, `h264_nvenc`, `libx264`, `av1_nvenc`. Wrong value causes encode failure if hardware not available. | Yes — active video codec row | `test_settings_risk_policy_rules.py` |
| `OutputContainer` | **High** | `mkv` or `mp4`. Affects subtitle compatibility and muxing behavior. | Yes — container policy row | `test_service_config_validation.py` |
| `EncodeThresholdGB` | **High** | Movie file size above which encode (rather than remux) is triggered. | Yes — route threshold row | `test_service_config_numeric_policy.py` |
| `TVEncodeThresholdGB` | **High** | TV episode size above which encode is triggered. | Yes — route threshold row | `test_service_config_numeric_policy.py` |
| `MovieRouteMaxVideoBitrateMbps` | **High** | Movie fallback bitrate cap when source height is unknown. Known-height sources use the resolution-aware bucket caps. | Yes — route bitrate row | `test_service_config_numeric_policy.py`, `test_stage_entrypoint.py` |
| `TVRouteMaxVideoBitrateMbps` | **High** | TV fallback bitrate cap when source height is unknown. Known-height sources use the resolution-aware bucket caps. | Yes — route bitrate row | `test_service_config_numeric_policy.py`, `test_stage_entrypoint.py` |
| `Route1080pBucketMaxHeight` | **High** | Source-height maximum for selecting the 1080-ish bitrate cap. Height selects the cap only; it does not force remux or encode. | Yes — route bitrate row | `test_service_config_numeric_policy.py`, `test_stage_entrypoint.py` |
| `Route1080pMaxVideoBitrateMbps` | **High** | Bitrate cap used for known-height sources in the 1080-ish bucket. | Yes — route bitrate row | `test_service_config_numeric_policy.py`, `test_stage_entrypoint.py` |
| `Route4KBucketMinHeight` | **High** | Source-height minimum for labeling the 4K bucket; heights between the two bucket boundaries use the 4K cap by default. | Yes — route bitrate row | `test_service_config_numeric_policy.py`, `test_stage_entrypoint.py` |
| `Route4KMaxVideoBitrateMbps` | **High** | Bitrate cap used for known-height 4K and between-bucket sources. | Yes — route bitrate row | `test_service_config_numeric_policy.py`, `test_stage_entrypoint.py` |
| `SizeGuardMode` | **High** | Post-encode size validation: `advisory` (warn), `strict` (fail if over), `off`. `strict` + aggressive growth settings blocks large encodes. | Yes — size guard posture row | `test_settings_risk_policy_rules.py` |
| `MaxEncodeGrowthPercent` | Medium | Allowed output size growth % for normal encodes before size guard triggers. | Yes — growth limit row | `test_service_config_numeric_policy.py` |
| `AllowH264RemuxIfPlexCompatible` | Medium | Allows H.264 sources to be remuxed (copy) rather than re-encoded when Plex-compatible. | Yes — H264 copy policy row | `test_service_config_option_policy.py` |
| `ReprocessAll` | **High** | Forces all sources to be reprocessed regardless of completed history. Blocked by save-readiness checklist pending confirmation. | Yes — reprocess flag warning row | `test_service_config_validation.py` |
| `MixPriorityPhase` | Medium | Mixes high-priority movie and TV items in one priority phase instead of separate media-type phases. | Yes — queue ordering handoff | `test_metadata_contract.py` |
| `QueueOrderingStrategy` | Medium | Default queue sort preset used when no explicit queue strategy command override is active. | Yes — queue ordering handoff | `test_metadata_contract.py` |

### Video Detail Group

| Key | Risk | Description | Launch handoff | Tests |
|---|---|---|---|---|
| `VideoPreset` | Medium | NVENC speed-quality tradeoff (p1–p7). Wrong value for hardware causes encoder rejection. | Yes — preset row | `test_service_config_option_policy.py` |
| `VideoQuality` | Medium | CQ/CRF target (18–28, default 22). Lower = larger files; higher = smaller/lower quality. | Yes — quality target row | `test_service_config_numeric_policy.py` |
| `ExtraVideoFlags` | **High** | Raw FFmpeg passthrough flags. Misconfiguration can corrupt output or crash encoder. Blocked by save-readiness checklist. | Yes — raw flags warning row | `test_settings_risk_policy_rules.py` |
| `FallbackCpuQuality` | Medium | CPU encode fallback CRF value. Used when GPU encode is unavailable. | Yes — CPU fallback row | `test_service_config_numeric_policy.py` |
| `FFmpegEncodeTimeoutSeconds` | Medium | GPU encode kill timer (default 21600s = 6h). Setting too low kills long encodes. | Not directly surfaced | `test_service_config_numeric_policy.py` |
| `MkvmergeRemuxTimeoutSeconds` | Medium | Remux timeout (default 7200s = 2h). | Not directly surfaced | `test_service_config_numeric_policy.py` |

### Audio Group

| Key | Risk | Description | Launch handoff | Tests |
|---|---|---|---|---|
| `AudioPassthroughProfile` | **High** | Audio policy: `plex_balanced`, `compatibility`, `lossless`, `custom`. Drives all passthrough vs. transcode decisions. | Yes — audio policy row | `test_service_config_profiles.py` |
| `CompatibleAudioCodecs` | **High** | Custom passthrough codec whitelist (when `AudioPassthroughProfile=custom`). Wrong codecs can cause silent transcoding of expected passthrough. | Yes — custom codec list row | `test_service_config_option_policy.py` |
| `AudioTranscodeCodec` | **High** | Fallback transcode codec: `eac3`, `ac3`, `aac`. Determines audio quality of non-passthrough tracks. | Yes — transcode codec row | `test_service_config_option_policy.py` |
| `AudioDownmixMode` | Medium | Channel preservation: `max_channels`, `preserve`, `stereo`. `stereo` force-downmixes all audio. | Yes — downmix policy row | `test_service_config_option_policy.py` |
| `AllowNoAudio` | **High** | When `true`, allows output with no audio track. Misconfiguration can silently produce silent files. Flagged as high-risk in risk policy. | Yes — no-audio risk warning | `test_settings_risk_policy_rules.py` |
| `AudioMaxChannels` | Medium | Max channel cap: 2, 6, or 8. | Yes — channel cap row | `test_service_config_numeric_policy.py` |

### Subtitle Group

| Key | Risk | Description | Launch handoff | Tests |
|---|---|---|---|---|
| `SubKeepLanguages` | **High** | Which subtitle languages are preserved in output. Wrong value silently drops subtitles. | Yes — subtitle language policy row | `test_service_config_option_policy.py` |
| `ConvertTx3gToSrt` | **High** | Whether TX3G (MP4 Timed Text) is converted to SRT. Affects subtitle output for MP4 sources. | Yes — TX3G policy row | `test_service_config_option_policy.py` |
| `ConvertBdpgsToSrt` | **High** | Whether BDPGS (Blu-ray PGS) subtitles are OCR'd to SRT. Requires `BdpgsOcrToolPath` to be valid. | Yes — BDPGS policy row | `test_settings_risk_policy_rules.py` |
| `DropTx3gAfterConversion` | Medium | Whether original TX3G track is removed after SRT conversion. | Yes — TX3G drop policy | `test_service_config_option_policy.py` |
| `DropBdpgsAfterConversion` | Medium | Whether original PGS track is removed after OCR. | Yes — BDPGS drop policy | `test_service_config_option_policy.py` |
| `BdpgsOcrToolPath` | **High** | Subtitle builder text field for PgsToSrt.exe/PgsToSrt.dll. Wrong/missing path causes silent OCR skip. Backend saved path evidence remains authoritative. | Not directly surfaced | `test_application_facade_web_static.py`, `test_facade_settings_policy.py`, `test_service_config_validation.py` |
| `BdpgsOcrTessdataPath` | **High** | Subtitle builder text field for Tesseract tessdata. Wrong path causes OCR garbage output. Backend saved path evidence remains authoritative. | Not directly surfaced | `test_application_facade_web_static.py`, `test_facade_settings_policy.py` |
| `SubSDHTitleKeywords` | Medium | Subtitle builder list field for title keywords that identify SDH tracks. Backend subtitle classification remains authoritative. | Not directly surfaced | `test_application_facade_web_static.py`, `test_service_config_validation.py` |
| `SubSupplementalKeywords` | Medium | Subtitle builder list field for title keywords that identify supplemental subtitle tracks. Backend subtitle classification remains authoritative. | Not directly surfaced | `test_application_facade_web_static.py`, `test_service_config_validation.py` |

### Runtime / Advanced Group

| Key | Risk | Description | Launch handoff | Tests |
|---|---|---|---|---|
| `LogRetentionDays` | Low | Log file rotation window (default 7 days). Low value causes older sessions to be deleted. | Not surfaced | `test_service_config_numeric_policy.py` |
| `TransientFailureRetryLimit` | Medium | Retry count before a source is marked as failed (default 3). Low values → sources fail faster. | Not surfaced | `test_service_config_numeric_policy.py` |
| `AllowSystemTools` | Medium | Allow PATH-based fallback for FFmpeg/mkvmerge. Enabling can use wrong tool versions. | Yes — system tools warning | `test_settings_risk_policy_rules.py` |
| `MinPipelineVersion` | Medium | Version floor for reprocessing. Sources processed by an older version are requeued. | Not surfaced | `test_service_config_validation.py` |
| `RobocopyTimeoutSeconds` | Medium | File transfer timeout (default 14400s = 4h). Low value kills in-progress transfers. | Not surfaced | `test_service_config_numeric_policy.py` |
| `ConsoleLogLevel` | Low | Console log verbosity. | Not surfaced | `test_service_config_validation.py` |
| `FileLogLevel` | Low | File log verbosity. | Not surfaced | `test_service_config_validation.py` |
| `ShowOverrides` | **High** | Advanced per-show media-policy override map. Wrong values can route, encode, audio, or subtitle-process matching shows unexpectedly. | Yes — settings policy impact rows | `test_metadata_contract.py` |

### Network Group

| Key | Risk | Description | Launch handoff | Tests |
|---|---|---|---|---|
| `NetworkRole` | **High** | `standalone`, `coordinator`, or `worker`. Changing while processing active jobs causes undefined state. | Yes — network role row | `test_application_facade_network.py`, `test_webview_network_read_only_boundary.py` |
| `CoordinatorPort` | Medium | HTTP listen port for coordinator (default 7830). Firewall must allow this port. | Not surfaced | `test_network_coordinator_source_policy.py` |
| `CoordinatorBindAddress` | Medium | `0.0.0.0` exposes coordinator on all interfaces; `127.0.0.1` restricts to localhost only. | Not surfaced | `test_network_coordinator_source_policy.py` |
| `CoordinatorAuthToken` | **Critical** | (Raw-only/hidden) Shared auth secret between coordinator and workers. | Not surfaced | Excluded from WebView by design |
| `WorkerCoordinatorUrl` | Medium | `http://host:port` of the coordinator. Must be reachable from this machine. | Not surfaced | `test_network_worker_source_policy.py` |
| `WorkerSourcePathMap` | Medium | Network builder JSON text field for worker path remapping. Misconfiguration causes workers to pick up wrong source locations. | Not surfaced | `test_network_worker_source_policy.py` |
| `WorkerConfigOverrides` | Medium | Network builder JSON text field for per-worker encode/routing overrides. Misconfiguration silently applies wrong policy to claimed jobs. | Not surfaced | `test_network_coordinator_source_policy.py` |
| `WorkerAuthToken` | **Critical** | (Raw-only/hidden) Must match `CoordinatorAuthToken`. | Not surfaced | Excluded from WebView by design |

---

## Settings-to-Launch Handoff Summary

The Launch page reads these config values (via `GET /api/launch/preflight` and `GET /api/snapshot`) and renders them as readiness rows in the Active Media Policy Boundary panel:

| Handoff row | Key(s) driving it |
|---|---|
| Route policy | `RoutingProfile`, `RouteThresholdMode`, `EncodeThresholdGB`, `TVEncodeThresholdGB`, `MovieRouteMaxVideoBitrateMbps`, `TVRouteMaxVideoBitrateMbps`, `Route1080pBucketMaxHeight`, `Route1080pMaxVideoBitrateMbps`, `Route4KBucketMinHeight`, `Route4KMaxVideoBitrateMbps` |
| Video codec / preset | `VideoCodec`, `VideoPreset`, `VideoQuality` |
| Audio policy | `AudioPassthroughProfile`, `AudioTranscodeCodec`, `AudioDownmixMode`, `AllowNoAudio` |
| Subtitle policy | `SubKeepLanguages`, `ConvertTx3gToSrt`, `ConvertBdpgsToSrt` |
| Deferred publish posture | `DeferredPublish`, `OutsourceMinFreeSpaceGB` |
| Path readiness | `SourceMovies`, `SourceTV`, `Outsource`, `LocalBase` |
| Size guard posture | `SizeGuardMode`, `MaxEncodeGrowthPercent` |
| System tool warnings | `AllowSystemTools`, `ExtraVideoFlags`, `ReprocessAll`, `AllowNoAudio` |
| Network role | `NetworkRole` |

All handoff rows are read-only. The Launch page cannot modify settings — changes must go through `POST /api/settings/save-patch`.

---

## See Also

- Settings builder coverage: `docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md`
- Risk policy rules: `tests/python/desktop/test_settings_risk_policy_rules.py`
- Network mode documentation: `docs/architecture/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`
- API route inventory: `docs/inventories/API_ROUTE_INVENTORY.md`
