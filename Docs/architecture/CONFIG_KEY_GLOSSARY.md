# Config Key Glossary

Last updated: 2026-05-19

Operator-friendly glossary for major settings and config keys. Intended for operators who want to understand what a key does before editing it, and for documentation authors writing about config behavior.

Sources: `Docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md`, `Pipeline/MediaPipeline_config_template.psd1`, WebView Settings builder labels.

This document does not invent defaults — all values noted here are from the current codebase. For the full list of keys and their WebView builder coverage status, see `Docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md`.

Code constants live in `DesktopApp/mediapipeline_desktop_app/config_keys.py` and `engine/config/config_keys.ps1`. Drift is guarded by `DesktopApp/tests/test_config_keys.py` and `Pipeline/Tests/Unit/Invoke-ConfigKeyRegistryChecks.ps1`.

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

## Routing and Encode Profile

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `RoutingProfile` | High-level route decision preset (e.g., Plex Direct Stream, forced encode) | Determines whether files are remuxed or encoded by default | Builder |
| `RouteThresholdMode` | Initial route threshold selector: `compatibility_advisory`, `size`, `bitrate`, `size_or_bitrate` | Chooses whether size, bitrate, or both can force encode before remux/copy | Builder |
| `SizeGuardMode` | How to enforce output size limits relative to source: `advisory`, `strict`, `off` | `strict` blocks completion if output is too large; `off` disables size check entirely | Builder |
| `MaxEncodeGrowthPercent` | Maximum allowed encode output size as a percentage of source size | Outputs that grow beyond this percentage fail in strict mode | Builder |
| `CompatibilityEncodeGrowthPercent` | Growth percent threshold used for compatibility-mode encode | Separate from MaxEncodeGrowthPercent to allow higher tolerance for compatibility encodes | Builder |
| `EncodeThresholdGB` | Source file size above which the pipeline considers the file for size-guard checks in movie mode | Files smaller than this may bypass size-guard in some routing profiles | Builder |
| `TVEncodeThresholdGB` | Same as EncodeThresholdGB but for TV episodes | Separate threshold for TV allows different policy by content type | Builder |
| `MovieRouteMaxVideoBitrateMbps` | Maximum estimated movie bitrate allowed for remux/copy routing | Sources above this bitrate are encoded unless folder policy overrides the route ceiling | Builder |
| `TVRouteMaxVideoBitrateMbps` | Maximum estimated TV bitrate allowed for remux/copy routing | Lets TV episodes use a lower bitrate ceiling than movies before encode is selected | Builder |
| `AllowH264RemuxIfPlexCompatible` | Allow H.264 sources that pass Plex compatibility to be remuxed instead of encoded | Disabling forces encode of all H.264 regardless of compatibility | Builder |
| `H264RemuxMaxBitrateMbps` | Maximum H.264 bitrate (Mbps) allowed for the remux-if-compatible path | Sources above this bitrate are encoded even if codec is compatible | Builder |
| `H264RemuxMaxHeight` | Maximum video height allowed for the remux-if-compatible path | Sources taller than this are encoded | Builder |
| `RemuxSafeVideoCodecs` | List of video codecs the pipeline treats as remux-safe | Codecs not in this list are always encoded | Builder |

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

## Output Container

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `OutputContainer` | Output file container format (e.g., mkv, mp4) | MP4 has limitations for some subtitle and audio track types | Builder |

---

## Subtitles

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `SubKeepLanguages` | Language codes for subtitle tracks to retain | Empty list retains no subtitles | Builder |
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
| `AudioTranscodeBitrate` | Fixed bitrate for transcoded audio | 0 = use AutoBitrateByChannels | Builder |
| `AudioTranscodeAutoBitrateByChannels` | Bitrate lookup by channel count for auto-bitrate transcodes | Allows stereo at lower bitrate than 5.1 | Builder |
| `AudioDownmixMode` | How to handle tracks with more channels than `AudioMaxChannels` | Forced stereo may lose surround | Builder |
| `AudioMaxChannels` | Maximum channel count for passthrough | Tracks with more channels are transcoded or downmixed | Builder |
| `PreferredDefaultAudioLanguages` | Language preference list for selecting default audio track | Affects which track plays by default in Plex | Builder |
| `AllowNoAudio` | Allow output files with no audio tracks | **High risk** — files with no audio tracks play silently; confirm this is intentional | Builder |

---

## Pending Publish and Recovery

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `DeferredPublish` | Enable parking of outputs locally when destination is unavailable | When enabled, outputs are not immediately published; drain is required later | Builder |
| `CleanupRemoteStaging` | Clean up remote staging after successful drain | Disabling leaves staging artifacts on the destination | Builder |
| `TransientFailureRetryLimit` | How many transient failures are retried before marking permanent | High limits may retry corrupted sources many times | Builder |
| `CleanupStaleAgeHours` | Age in hours after which stale scratch/staging files are cleaned up | Too low may clean up files from ongoing operations | Builder |
| `RobocopyTimeoutSeconds` | Per-file timeout for Robocopy publish/transfer operations | Too low may cause false timeout failures on slow networks | Builder |
| `RobocopyFlags` | Custom flags appended to Robocopy commands | Raw passthrough — incorrect flags can cause overwrite or mirror behavior | Builder |

---

## Runtime and Diagnostics

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `DebugMode` | Enable verbose debug logging | Produces large log files; not for production use | Builder |
| `LogRetentionDays` | How many days of run logs to retain before cleanup | Low values may delete logs before a failure is investigated | Builder |
| `FFmpegEncodeTimeoutSeconds` | Per-file timeout for NVENC encodes | Too low kills slow encodes prematurely | Builder |
| `FFmpegRemuxTimeoutSeconds` | Per-file timeout for remux operations | Lower than encode timeout is usually safe | Builder |
| `FFmpegCpuEncodeTimeoutSeconds` | Per-file timeout for CPU fallback encodes | CPU encodes are slower than NVENC; set appropriately | Builder |
| `MkvmergeRemuxTimeoutSeconds` | Per-file timeout for MKVToolNix remux operations | Too low kills slow remux operations; default 2h is suitable for most sources | Builder |
| `SourceScanIntervalSeconds` | How often the pipeline scans for new source files | Lower = more responsive to new files; higher = less I/O | Builder |
| `AllowSystemTools` | Allow falling back to system-PATH FFmpeg/MKVToolNix instead of bundled tools | Risky — system tools may be different versions than tested | Builder |
| `ConsoleLogLevel` | Log level for console output (e.g., WARNING, INFO, DEBUG) | **Builder** — added to Runtime builder in settingsMetadata.js | Builder |
| `FileLogLevel` | Log level for file-based log output | **Builder** — added to Runtime builder in settingsMetadata.js | Builder |

---

## Queue and Reprocess

| Key | Purpose | Risk note | Builder |
|---|---|---|---|
| `PriorityMarkers` | Strings in filenames that mark a file for priority processing | Default: `!` and `[NOW]`; `!` is preferred | Builder |
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
| `WorkerConfigOverrides` | JSON per-worker config overrides applied at job-claim time | Network builder JSON text field; advanced multi-worker policy still needs backend Preview/Save | Builder |
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

- Full coverage matrix: `Docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md`
- Raw-key priority ranking: `Docs/architecture/SETTINGS_RAW_KEY_TRIAGE.md`
- Settings builder WebView page: `GET /api/settings/workspace`
- Hidden auth-key fields: `Docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md`
