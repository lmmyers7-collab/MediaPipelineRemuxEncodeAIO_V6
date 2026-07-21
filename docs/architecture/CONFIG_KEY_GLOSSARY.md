# Config Key Glossary

Last updated: 2026-07-15

Operator-friendly glossary for major settings and config keys. Intended for operators who want to understand what a key does before editing it, and for documentation authors writing about config behavior.

Sources: `docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md`, `ops/pipeline/config/MediaPipeline_config_template.psd1`, WebView Settings builder labels.

This document does not invent defaults — all values noted here are from the current codebase. For the full list of keys and their WebView builder coverage status, see `docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md`.

Code constants live in `src/mediapipeline/desktop/config_keys.py` and `ops/pipeline/engine/config/config_keys.ps1`. Drift is guarded by `tests/python/desktop/test_config_keys.py` and `ops/pipeline/tests/Unit/Invoke-ConfigKeyRegistryChecks.ps1`.

---

## Notation

- **Builder**: Has a structured WebView builder field. Adjustable via Settings page.
- **Raw/Advanced**: Must be edited via raw JSON patch in the Settings page or by editing the config file directly.
- **Risk note**: What can go wrong if this key is misconfigured.
- **Raw-Key Action Plan**: Settings page read-only panel that groups schema drift, BDPGS OCR path evidence, subtitle keyword builder coverage, intentionally excluded network auth secrets, remaining advanced raw keys, and backend-owned mutation boundaries before the operator edits raw JSON.

---

## Source, Output, and Scratch Paths

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `SourceMovies` | Root path where movie source files are scanned | Wrong path = nothing in queue | Builder |
| `SourceTV` | Root path where TV source files are scanned | Wrong path = nothing in queue | Builder |
| `Outsource` | Output destination for processed files (final destination) | Wrong path may cause deferred publish or parking | Builder |
| `LocalBase` | Base path for all runtime state: queue, completed, failures, pending publish | If changed, old state becomes orphaned at the previous path | Builder |

---

## File Safety and Stability

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `FileStabilityWait` | Seconds to wait after a source file stops growing before processing it | Too low = processes files still being copied (partial input); too high = delayed processing of fast-arriving files | Builder |
| `SkipStabilityCheck` | Skip the file-stability wait | Risky on network shares or slow copy operations | Builder |
| `EnableIntegrityCheck` | Run an ffprobe integrity check on the output before accepting it | Disabling this means corrupted outputs may pass undetected | Builder |
| `ValidExtensions` | List of file extensions the pipeline considers valid media | Files with other extensions are skipped silently | Builder |
| `MinFreeSpaceGB` | Minimum free space on the output destination before processing | Prevents out-of-space failures mid-encode; low-space parking is triggered when this is breached | Builder |
| `OutsourceMinFreeSpaceGB` | Minimum free space on the outsource destination for deferred publish | Too low may allow drain to run when destination is nearly full | Builder |

---

## Watch Folders

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `EnableWatchFolders` | Enables the local desktop watch-folder manager | Disabled by default; enabling causes the desktop API host to scan configured/derived source roots for newly stable files | Builder |
| `WatchFolderRoots` | Explicit roots scanned by the watch-folder manager; empty means derive from configured source/library-profile roots | Wrong roots can miss new files or scan too broadly; source files are never deleted or overwritten by the watcher | Builder |
| `WatchDebounceSeconds` | Seconds a discovered file must remain unchanged before it is treated as stable | Too low can notice files before copy completion; too high delays enqueue/launch response | Builder |
| `WatchAction` | Watch response: `enqueue_only` records pending work; `enqueue_and_launch` requests backend Run Once | Launch remains backend-owned and still goes through `/api/pipeline/start` guards | Builder |
| `WatchRespectScheduleWindow` | Keeps watch-triggered launch requests schedule-gated when true | Setting false sends an explicit ignore-schedule override for watch-triggered launches | Builder |

---

## Routing and Encode Profile

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `RoutingProfile` | High-level route decision preset (e.g., Plex Direct Stream, forced encode) | Determines whether files are remuxed or encoded by default | Builder |
| `RouteThresholdMode` | Initial route threshold selector: `compatibility_advisory`, `size`, `bitrate`, `size_or_bitrate` | Chooses whether size, bitrate, or both can force encode before remux/copy | Builder |
| `SizeGuardMode` | How to enforce output size limits relative to source: `advisory`, `strict`, `off` | `strict` blocks completion if output is too large; `off` disables size check entirely | Builder |
| `MaxEncodeGrowthPercent` | Maximum allowed encode output size as a percentage of source size | Outputs that grow beyond this percentage fail in strict mode | Builder |
| `CompatibilityEncodeGrowthPercent` | Growth percent threshold used for compatibility-mode encode | Separate from MaxEncodeGrowthPercent to allow higher tolerance for compatibility encodes | Builder |
| `MovieRoute1080pTargetSizeGB` | Movie target output size for the 1080p bucket | Unknown-height movies use this target | Builder |
| `TVRoute1080pTargetSizeGB` | TV target output size for the 1080p bucket | Unknown-height TV uses this target | Builder |
| `Route1080pUpperHeightTolerancePercent` | Percent above 1080p used to derive the 1080p bucket ceiling | Replaces the old raw 1080p height setting; persisted config stores the percent | Builder |
| `Route1080pMaxVideoBitrateMbps` | Maximum duration-derived bitrate for sources in the 1080p bucket | Unknown-height sources use this cap before bitrate-capable modes can force encode | Builder |
| `Route4KLowerHeightTolerancePercent` | Percent below 2160p used to derive the 4K bucket start | Replaces the old raw 4K height setting; persisted config stores the percent | Builder |
| `Route4KMaxVideoBitrateMbps` | Maximum duration-derived bitrate for the 4K and in-between buckets | Used for known-height sources above the 1080-ish bucket before bitrate-capable modes can force encode | Builder |
| `AllowH264RemuxIfPlexCompatible` | Allow H.264 sources that pass Plex compatibility to be remuxed instead of encoded | Disabling forces encode of all H.264 regardless of compatibility | Builder |
| `H264RemuxMaxBitrateMbps` | Maximum H.264 bitrate (Mbps) allowed for the Plex-compatible H.264 shortcut and effective H.264 copy scoring | Not a universal remux safety blocker; codec-safe fallback can still remux when hard routing does not force encode | Builder |
| `H264RemuxMaxHeight` | Maximum video height allowed for the Plex-compatible H.264 shortcut | Not a universal remux safety blocker; taller H.264 can still remux later when codec-safe fallback allows it | Builder |
| `RemuxSafeVideoCodecs` | List of video codecs the pipeline treats as remux-safe | Codecs not in this list are always encoded | Builder |

Bitrate route decisions use bitrate estimated from `file_size_bytes` and `duration_seconds`. Source height selects the 1080p, 1440p, or 4K bitrate cap when height is known; unknown height uses the 1080p target and 1080p bitrate cap. When duration is missing or zero, bitrate routing does not fall back to `source_media_profile.estimated_bitrate_mbps`; the route evidence reports zero estimated bitrate and the bitrate filter does not fire.

---

## Video Encoder Settings

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `VideoCodec` | Output video codec for encodes (e.g., H.264 NVENC) | Wrong value may produce unsupported output for Plex | Builder |
| `VideoPreset` | NVENC encoding speed/quality preset | Faster presets may reduce quality | Builder |
| `VideoQuality` | NVENC CQ (constant quality) value | Lower = better quality, higher filesize; higher = worse quality | Builder |
| `CpuEncodePreset` | FFmpeg CPU encoding preset (e.g., slow, medium, fast) | Only active when NVENC is unavailable | Builder |
| `FallbackCpuQuality` | CRF value for CPU fallback encodes | Same quality tradeoff as VideoQuality | Builder |
| `CpuEncodeProcessPriority` | OS process priority for CPU encode jobs | Below normal priority prevents encode from starving the system | Builder |
| `CpuEncodeMaxThreads` | Thread count cap for CPU encodes | Caps CPU usage; 0 = no cap | Builder |
| `ExtraVideoFlags` | Raw FFmpeg video flags appended to encode commands | **High risk** — raw FFmpeg passthrough; errors may produce silent corruption or failed encodes | Builder |

---

## Quality Verification

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `EnableQualityVerification` | Enables objective source-vs-output metric checks after lossy encodes | Disabled by default; enabling should be validated with representative media before unattended runs | Builder |
| `QualityMetric` | Metric used for the comparison: `vmaf`, `ssim`, or `psnr` | Threshold units differ by metric: VMAF 0-100, SSIM 0-1, PSNR dB | Builder |
| `QualitySampleMode` | Chooses sampled windows or full-file measurement | Full-file quality checks can be expensive on long movies | Builder |
| `QualitySampleSeconds` | Seconds measured per sampled window | Larger windows improve signal but increase FFmpeg verification runtime | Builder |
| `QualitySampleCount` | Number of sampled windows measured | More windows improve coverage but increase FFmpeg verification runtime | Builder |
| `QualityWarnThreshold` | Score below this tier is recorded as quality-review evidence | Zero disables this tier; threshold units follow `QualityMetric` | Builder |
| `QualityFailThreshold` | Score below this tier is recorded as below-floor quality evidence | Zero disables this tier; with `block_review`, below-floor encodes do not publish | Builder |
| `QualityFailAction` | Action for below-floor encodes: `warn_only` or `block_review` | `block_review` rejects the encode before publish and routes the source to operator review | Builder |
| `QualityVerifyTimeoutSeconds` | FFmpeg timeout for each quality verification run | Tool errors and timeouts fail open with error evidence rather than blocking publish | Builder |

---

## Output Container

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `OutputContainer` | Output file container format (e.g., mkv, mp4) | MP4 has limitations for some subtitle and audio track types | Builder |

---

## Subtitles

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `SubKeepLanguages` | Language codes for subtitle tracks to retain | Empty list retains no subtitles | Builder |
| `AllowSubtitleHelperFallback` | Allow degraded launch if the bundled ASS/SSA helper startup self-check fails | Default `false` blocks launch so broken subtitle conversion is visible before unattended work | Builder |
| `ConvertTx3gToSrt` | Convert TX3G (MP4 embedded) subtitle tracks to SRT | Disabling this drops TX3G subtitles unless `Tx3gPreserveExistingSrt` saves them | Builder |
| `DropTx3gAfterConversion` | Drop the TX3G track after SRT is produced | Keeping both TX3G and SRT is usually redundant | Builder |
| `ConvertBdpgsToSrt` | Convert BDPGS (Blu-ray PGS) subtitle tracks to SRT via OCR | Requires `BdpgsOcrToolPath` and tessdata | Builder |
| `BdpgsOcrToolPath` | Path to the PgsToSrt OCR executable | Builder text field; backend Preview/Save and saved path evidence remain authoritative | Builder |
| `BdpgsOcrTessdataPath` | Path to the tessdata folder for OCR | Builder text field; backend Preview/Save and saved path evidence remain authoritative | Builder |
| `MergeThresholdMs` | Milliseconds threshold for merging adjacent subtitle cues | Too aggressive merging may combine separate lines incorrectly | Builder |
| `ExcludeSubtitleStyles` | ASS/SSA style names to drop from subtitle tracks | Useful for removing karaoke or SDH-only styles | Builder |
| `IncludeSubtitleStyles` | ASS/SSA style names to explicitly keep | Overrides ExcludeSubtitleStyles for listed style names | Builder |
| `DropAssAfterConversion` | Drop ASS/SSA subtitle tracks after SRT conversion | Keeps output smaller; review if ASS formatting is needed downstream | Builder |
| `RemoveKaraoke` | Strip karaoke-tagged cues from subtitle output | Safe for most media | Builder |
| `SubSDHTitleKeywords` | Keyword list used to identify SDH (subtitle for the deaf and hard of hearing) tracks by title | Builder list field; backend subtitle classification remains authoritative | Builder |
| `SubSupplementalKeywords` | Keyword list used to identify supplemental subtitle tracks | Builder list field; backend subtitle classification remains authoritative | Builder |

---

## Audio

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `AudioPassthroughProfile` | Named profile controlling which audio codecs pass through without transcoding | Passthrough tracks are preserved as-is; wrong profile may force transcoding of compatible tracks | Builder |
| `CompatibleAudioCodecs` | Explicit list of codecs treated as passthrough-compatible | Codecs not in this list are transcoded | Builder |
| `AudioTranscodeCodec` | Target codec for audio that must be transcoded | Must be a codec Plex and the player support | Builder |
| `AudioTranscodeBitrate` | Fixed bitrate for transcoded audio when automatic channel-based bitrate is off | Invalid or unsuitable values can starve or bloat normalized tracks | Builder |
| `AudioTranscodeAutoBitrateByChannels` | Bitrate lookup by channel count for auto-bitrate transcodes | Allows stereo at lower bitrate than 5.1 | Builder |
| `AudioDownmixMode` | How to handle tracks with more channels than `AudioMaxChannels` | Forced stereo may lose surround | Builder |
| `AudioMaxChannels` | Maximum channel count for transcodes when `AudioDownmixMode` caps channels | Low caps downmix surround during normalization; passthrough copies are not channel-capped | Builder |
| `PreferredDefaultAudioLanguages` | Language preference list for selecting default audio track | Affects which track plays by default in Plex | Builder |
| `AllowNoAudio` | Allow output files with no audio tracks | **High risk** — files with no audio tracks play silently; confirm this is intentional | Builder |

---

## Pending Publish and Recovery

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `DeferredPublish` | Enable parking of outputs locally when destination is unavailable | When enabled, outputs are not immediately published; drain is required later | Builder |
| `PendingPublishDrainMode` | Deferred publish drain posture: `manual` or explicit backend-owned `trusted` drain | `trusted` can move trusted parked manifests unattended; keep `manual` unless soak validation proves the path safe | Builder |
| `PendingPublishDrainBatchSize` | Maximum pending-publish manifests drained per normal/trusted batch | Too high can monopolize publish time after destination recovery; too low slows backlog recovery | Builder |
| `CleanupRemoteStaging` | Clean up remote staging after successful drain | Disabling leaves staging artifacts on the destination | Builder |
| `TransientFailureRetryLimit` | How many transient failures are retried before marking permanent | High limits may retry corrupted sources many times | Builder |
| `CleanupStaleAgeHours` | Age in hours after which stale scratch/staging files and empty local encoded-output folders are cleaned up | Too low may clean up folders from recent operations | Builder |
| `RobocopyTimeoutSeconds` | Per-file timeout for Robocopy publish/transfer operations | Too low may cause false timeout failures on slow networks | Builder |
| `RobocopyFlags` | Custom flags appended to Robocopy commands | Raw passthrough — incorrect flags can cause overwrite or mirror behavior | Builder |

---

## Runtime and Diagnostics

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `DebugMode` | Enable verbose debug logging | Produces large log files; not for production use | Builder |
| `LogRetentionDays` | How many days of run logs to retain before cleanup | Low values may delete logs before a failure is investigated | Builder |
| `InterruptedToolLogRetentionDays` | How many days to retain stopped or force-terminated native-tool diagnostics (default `3`, range `1`–`365`) | Low values shorten post-stop evidence; these logs remain separate from failure artifacts | Builder |
| `PipelineDebugLogMaxBytes` | Size cap for live `pipeline_debug.log` rotation | Too low rotates evidence too often; too high delays recovery from runaway debug logging | Builder |
| `FailureArtifactWarningThresholdGB` | Home/Reports warning threshold for captured failure artifact storage | Set to `0` only to disable the toast; the read-only summary remains visible | Builder |
| `FailureArtifactRetentionDays` | Reports cleanup age threshold for captured failure artifacts | Set to `0` to disable age-based artifact cleanup; policy cleanup can use the current backend plan with confirmation | Builder |
| `FailureArtifactCleanupTargetGB` | Reports cleanup target-size threshold for captured failure artifacts | Set to `0` to disable target-size artifact cleanup; policy cleanup can use the current backend plan with confirmation | Builder |
| `FFmpegEncodeTimeoutSeconds` | Per-file timeout for NVENC encodes | Too low kills slow encodes prematurely | Builder |
| `FFmpegRemuxTimeoutSeconds` | Per-file timeout for remux operations | Lower than encode timeout is usually safe | Builder |
| `FFmpegCpuEncodeTimeoutSeconds` | Per-file timeout for CPU fallback encodes | CPU encodes are slower than NVENC; set appropriately | Builder |
| `MkvmergeRemuxTimeoutSeconds` | Per-file timeout for MKVToolNix remux operations | Too low kills slow remux operations; default 2h is suitable for most sources | Builder |
| `SourceScanIntervalSeconds` | How often the pipeline scans for new source files | Lower = more responsive to new files; higher = less I/O | Builder |
| `ConsecutiveRoundFailureBlockLimit` | Continuous-mode unexpected round failure threshold before blocked probe backoff | Too low can pause useful recovery; too high delays blocked-health visibility | Raw/Advanced |
| `ConsecutiveRoundFailureProbeBackoffSeconds` | Backoff between blocked continuous-mode recovery probes | Too low can churn logs/processes; too high delays recovery after transient issues | Raw/Advanced |
| `PendingPublishBacklogBlockThreshold` | Non-deferred pending-publish backlog count that blocks new queue work | Too high allows parked outputs to accumulate; too low can stall processing during normal drain delay | Raw/Advanced |
| `PendingPublishDeferredBlockThreshold` | Deferred pending-publish backlog count that blocks new queue work | Too high allows deferred parked outputs to accumulate; does not force-drain manifests | Raw/Advanced |
| `PauseFlagReviewSeconds` | Pause-flag age for review health | Does not auto-clear pause; low values increase review noise | Raw/Advanced |
| `PauseFlagBlockSeconds` | Pause-flag age for blocked autonomy health | Does not auto-clear pause; high values delay unattended blocked-health visibility | Raw/Advanced |
| `LocalWorkerHeartbeatGraceSeconds` | Grace window for stale local worker child heartbeat evidence | Too low can reclaim slow-but-live workers; too high delays stale slot recovery | Raw/Advanced |
| `QueueExecutionMaxRunnablePerRound` | Maximum runnable queue items processed in one engine round | Too high increases per-round memory/work; too low increases round churn | Raw/Advanced |
| `QueueLaunchSnapshotFreshnessSeconds` | Age threshold for labeling queue-snapshot generation and file timestamps as older-than-preferred preview evidence (default `60`, range `15`–`3600`); age never blocks Run Once because runtime rebuilds and fingerprint-verifies the plan | Too low creates advisory refresh churn; it does not change launch authority | Builder/Advanced |
| `StateDbMaintenanceIntervalSeconds` | Best-effort SQLite mirror maintenance interval | JSON remains authoritative; low values add maintenance overhead | Raw/Advanced |
| `StateDbWalReviewBytes` | SQLite mirror WAL review/maintenance threshold | JSON remains authoritative; high values allow larger WAL growth before review | Raw/Advanced |
| `StateDbCompletedJobsMaxRows` | Maximum completed-job rows retained in the SQLite mirror | JSONL completed manifests remain authoritative; too low reduces mirror history, too high increases SQLite growth | Raw/Advanced |
| `AutonomyPendingReviewSeconds` | Pending-publish age review threshold for autonomy diagnostics | Backend-only; does not drain, repair, or mutate manifests | Raw/Advanced |
| `AutonomyPendingBlockSeconds` | Pending-publish age block threshold for autonomy diagnostics | Backend-only; pending publish remains manifest-backed | Raw/Advanced |
| `AutonomyPendingRetryBlockCount` | Pending-publish retry-count block threshold | Backend-only; low values may block new autonomy sooner | Raw/Advanced |
| `AutonomyPendingTotalReviewBytes` | Pending-publish total-byte review threshold | Publish & Recovery builder control; UI edits in GiB and saves byte-backed config; does not drain parked output | Builder |
| `AutonomyPendingTotalBlockBytes` | Pending-publish total-byte block threshold | Publish & Recovery builder control for the launch-block budget; UI edits in GiB and saves byte-backed config; does not force-drain parked output | Builder |
| `AutonomyFailureOperatorRequiredBlockSeconds` | Age threshold for operator-required failure blockers | Backend-only failure evidence; does not clean artifacts | Raw/Advanced |
| `AutonomyFailureOperatorRequiredBlockCount` | Count threshold for operator-required failure blockers | Backend-only failure evidence; low values may block sooner | Raw/Advanced |
| `AutonomyFailureInfrastructureBlockCount` | Count threshold for infrastructure failure blockers | Backend-only failure evidence; low values may block sooner | Raw/Advanced |
| `AutonomyActiveJobTimeoutGraceSeconds` | Passive ActiveJobs stale grace after native timeout evidence | Stale ActiveJobs evidence is review-only and does not authorize process kills | Raw/Advanced |
| `AutonomyActiveJobNoTimeoutBlockSeconds` | Passive ActiveJobs stale threshold without native timeout evidence | Stale ActiveJobs evidence is review-only and does not block launch by itself | Raw/Advanced |
| `AutonomyStorageMinFreeGB` | Autonomy diagnostics storage floor when path health has no reserve | Backend-only read-only budget evidence | Raw/Advanced |
| `AutonomyStateFileReviewBytes` | State/journal file size review threshold | Backend-only read-only state growth evidence | Raw/Advanced |
| `AutonomyStateFileBlockBytes` | State/journal file size block threshold | Backend-only read-only state growth evidence | Raw/Advanced |
| `AutonomyScanLimit` | File enumeration cap for autonomy diagnostics | Truncated scans are reported as lower bounds | Raw/Advanced |
| `AutonomyGrowthSnapshotMaxCount` | Retained diagnostics growth snapshot count | Snapshot writes are explicit diagnostics-state writes only | Raw/Advanced |
| `AutonomyWatchdogRecordLimit` | Returned passive ActiveJobs watchdog record cap | Total and truncation counts remain visible | Raw/Advanced |
| `AllowSystemTools` | Allow falling back to system-PATH FFmpeg/MKVToolNix instead of bundled tools | Risky — system tools may be different versions than tested | Builder |
| `ConsoleLogLevel` | Log level for console output (e.g., WARNING, INFO, DEBUG) | **Builder** — added to Runtime builder in settingsMetadata.js | Builder |
| `FileLogLevel` | Log level for file-based log output | **Builder** — added to Runtime builder in settingsMetadata.js | Builder |
| `ShowOverrides` | Advanced mapping of show-name patterns to per-show routing, video, audio, and subtitle overrides | High-risk media-policy override; verify through backend Preview Patch before saving | Raw/Advanced |

---

## Queue and Reprocess

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `PriorityMarkers` | Strings in filenames that mark a file for priority processing | Default: `!` and `[NOW]`; `!` is preferred | Builder |
| `MixPriorityPhase` | Process high-priority movie and TV items in one mixed priority phase | Can change queue ordering across libraries; review before launch | Raw/Advanced |
| `QueueOrderingStrategy` | Default queue sort preset when no explicit queue strategy command override is active | Changes processing order, not media policy; verify Launch scope before starting | Raw/Advanced |
| `MinPipelineVersion` | Minimum acceptable pipeline version for processing sidecars | Used to prevent old sidecars from being trusted; not a display label | Builder |
| `ReprocessAll` | Force all sources to be re-processed, ignoring completed-manifest exclusions | **High risk** — re-queues already-completed files; confirm explicitly | Builder |
| `ProcessedIndexRefreshSeconds` | How often the processed-file index is refreshed | Lower values detect newly completed files faster | Builder |
| `CreateTVSubfolder` | Create `Show/Season XX/` subfolder structure (Plex layout) in the output | Disabling flattens TV output to a single folder; affects downstream Plex library scanning | Builder |

---

## Network Mode (Non-Secret Keys)

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `NetworkRole` | Role of this instance: `standalone`, `coordinator`, or `worker` | Standalone is the supported default; network mode is experimental | Builder |
| `CoordinatorPort` | TCP port the coordinator listens on | Must be reachable by all workers | Builder |
| `CoordinatorAlsoEncodeLocally` | Whether the coordinator also processes files locally | Disabling leaves coordinator as dispatch-only | Builder |
| `WorkerCoordinatorUrl` | URL the worker uses to reach the coordinator | Must include scheme and port | Builder |
| `WorkerName` | Identifier for this worker in coordinator logs | Useful for multi-worker environments | Builder |
| `WorkerSourcePathMap` | JSON map of coordinator source paths to local worker equivalents | Network builder JSON text field; backend Preview/Save validates the config shape | Builder |
| `WorkerConfigOverrides` | Compatibility-only legacy per-worker override JSON; backend network workers no longer apply it at claim time | Network builder labels this backend-disabled compatibility surface; use current worker policy keys for supported execution behavior | Compatibility (backend-disabled) |
| `CoordinatorAuthToken` | **Raw/Advanced** — coordinator auth secret | Must not appear in WebView builder; edit only via raw JSON or config file directly | Raw (intentionally hidden from WebView) |
| `WorkerAuthToken` | **Raw/Advanced** — worker auth secret | Same as CoordinatorAuthToken | Raw (intentionally hidden from WebView) |

---

## Raw-Key Action Plan

The WebView Settings page includes a read-only Raw-Key Action Plan. It does not stage, validate, or save settings; it explains which raw-key category needs attention:

| Category | Operator meaning |
|---|---|
| Schema drift | Unknown keys require backend Preview Patch before save. |
| BDPGS OCR paths | OCR tool/tessdata paths are Subtitle builder text fields with backend-authored saved path evidence. |
| Subtitle keyword lists | SDH/supplemental keyword lists are Subtitle builder list fields; backend classification remains authoritative. |
| Network auth secrets | Auth tokens stay intentionally excluded from builders and must remain redacted. |
| Mutation boundary | Preview/Save remains backend-owned; WebView cannot edit secrets, resolve arbitrary paths, run OCR/FFmpeg, launch, publish/drain, rename, or touch media from this panel. |

---

## See Also

- Full coverage matrix: `docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md`
- Raw-key priority ranking: `docs/architecture/SETTINGS_RAW_KEY_TRIAGE.md`
- Settings builder WebView page: `GET /api/settings/workspace`
- Hidden auth-key fields: `docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md`
