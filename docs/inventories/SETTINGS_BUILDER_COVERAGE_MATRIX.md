# Settings Builder Coverage Matrix

Maps every known `CONFIG_FIELD_DEFINITIONS` key to its WebView settings builder coverage, as of the current state. This is a read-only audit document. It does not implement builder changes.

Total backend metadata keys: 172 (from `CONFIG_FIELD_DEFINITIONS` and the config contract).
Covered by structured WebView builder arrays: 141.
Handled by the dedicated Library Profiles editor: 1 (`LibraryProfiles`).
Known advanced/direct-config metadata without a routine structured builder: 28.
Intentionally hidden auth secrets: 2.

---

## Builder Groups

| Builder name | Fields covered | Purpose |
|---|---|---|
| Routing / Size | `RoutingProfile`, `RouteThresholdMode`, `SizeGuardMode`, `EncodeTuningPreset`, `EncodeLadder`, `VideoCodec`, `OutputContainer`, `MaxEncodeGrowthPercent`, `CompatibilityEncodeGrowthPercent`, `MovieRoute1080pTargetSizeGB`, `MovieRoute1440pTargetSizeGB`, `MovieRoute4KTargetSizeGB`, `TVRoute1080pTargetSizeGB`, `TVRoute1440pTargetSizeGB`, `TVRoute4KTargetSizeGB`, `Route1080pUpperHeightTolerancePercent`, `Route1080pMaxVideoBitrateMbps`, `Route1440pLowerHeightTolerancePercent`, `Route1440pUpperHeightTolerancePercent`, `Route1440pMaxVideoBitrateMbps`, `Route4KLowerHeightTolerancePercent`, `Route4KMaxVideoBitrateMbps` | High-level route, per-height target, resolution-selected bitrate, and size policy |
| Video Detail | `VideoPreset`, `VideoQuality`, `AllowH264RemuxIfPlexCompatible`, `H264RemuxMaxBitrateMbps`, `H264RemuxMaxHeight`, `RemuxSafeVideoCodecs`, `FallbackCpuQuality`, `CpuEncodePreset`, `CpuEncodeProcessPriority`, `CpuEncodeMaxThreads`, `ExtraVideoFlags` | NVENC/CPU encoder precision and copy policy |
| Quality Verification | `EnableQualityVerification`, `QualityMetric`, `QualitySampleMode`, `QualitySampleSeconds`, `QualitySampleCount`, `QualityWarnThreshold`, `QualityFailThreshold`, `QualityFailAction`, `QualityVerifyTimeoutSeconds` | Post-encode objective metric, sampling window, warning/failure thresholds, review action, and verification timeout |
| File Safety / Publish | `SourceMovies`, `SourceTV`, `Outsource`, `LocalBase`, `MinFreeSpaceGB`, `OutsourceMinFreeSpaceGB`, `FileStabilityWait`, `WatchDebounceSeconds`, `WatchFolderRoots`, `WatchAction`, `EnableWatchFolders`, `WatchRespectScheduleWindow`, `CleanupStaleAgeHours`, `OutputSizeMultiplier`, `ValidExtensions`, `RobocopyFlags`, `DeferredPublish`, `PendingPublishDrainMode`, `PendingPublishDrainBatchSize`, `AggressiveEpisodeParsing`, `SkipStabilityCheck`, `EnableIntegrityCheck`, `CreateTVSubfolder`, `CleanupRemoteStaging` | Source/output/scratch paths, stability, watch-folder intake, integrity, deferred publish |
| Pending Publish / Recovery | `DeferredPublish`, `PendingPublishDrainMode`, `PendingPublishDrainBatchSize`, `CleanupRemoteStaging`, `TransientFailureRetryLimit`, `CleanupStaleAgeHours`, `RobocopyTimeoutSeconds`, `RobocopyFlags`, `OutsourceMinFreeSpaceGB`, `OutputSizeMultiplier`, `EnableIntegrityCheck`, `SkipStabilityCheck` | Drain behavior and recovery tuning |
| Audio | `AudioPassthroughProfile`, `CompatibleAudioCodecs`, `PreferredDefaultAudioLanguages`, `AudioTranscodeCodec`, `AudioTranscodeBitrate`, `AudioTranscodeAutoBitrateByChannels`, `AudioDownmixMode`, `AudioMaxChannels`, `AllowNoAudio` | Passthrough, transcode, channel, language policy |
| Subtitle | `SubKeepLanguages`, `AllowSubtitleHelperFallback`, `Tx3gExtractLanguages`, `BdpgsExtractLanguages`, `MergeThresholdMs`, `SubtitleExtractTimeoutSeconds`, `SubtitleProbeTimeoutSeconds`, `BdpgsOcrTimeoutSeconds`, `BdpgsOcrToolPath`, `BdpgsOcrTessdataPath`, `SubSDHTitleKeywords`, `SubSupplementalKeywords`, `ExcludeSubtitleStyles`, `IncludeSubtitleStyles`, `ConvertTx3gToSrt`, `DropTx3gAfterConversion`, `CreateExternalTx3gSrtSidecars`, `Tx3gPreserveExistingSrt`, `Tx3gTreatForcedAsSeparate`, `TreatTx3gSignsSongsAsForced`, `ConvertBdpgsToSrt`, `DropBdpgsAfterConversion`, `TreatBdpgsSignsSongsAsForced`, `DropAssAfterConversion`, `RemoveKaraoke`, `StripFormatting`, `MergeAdjacent`, `KeepSignsAndSongs`, `TreatAssSignsSongsAsForced` | TX3G, BDPGS OCR, ASS/SSA drop/convert/preserve, SDH/supplemental keyword classification inputs |
| Runtime / Diagnostics | `DebugMode`, `ConsoleLogLevel`, `FileLogLevel`, `LogRetentionDays`, `PipelineDebugLogMaxBytes`, `FailureArtifactWarningThresholdGB`, `FailureArtifactRetentionDays`, `FailureArtifactCleanupTargetGB`, `FFmpegEncodeTimeoutSeconds`, `FFmpegRemuxTimeoutSeconds`, `FFmpegCpuEncodeTimeoutSeconds`, `RobocopyTimeoutSeconds`, `SourceScanIntervalSeconds`, `SourceScanTimeoutSeconds`, `IndexScanTimeoutSeconds`, `CleanupScanTimeoutSeconds`, `TransientFailureRetryLimit`, `AllowSystemTools`, `MkvmergeRemuxTimeoutSeconds` | Logging, scan cadence, timeout, retry, PATH fallback, failure-artifact warning and cleanup thresholds |
| Queue / Reprocess | `PriorityMarkers`, `ProcessedIndexRefreshSeconds`, `MinPipelineVersion`, `ReprocessAll` | Priority markers, index refresh, reprocess mode |
| Network | `NetworkRole`, `CoordinatorPort`, `CoordinatorBindAddress`, `CoordinatorAlsoEncodeLocally`, `CoordinatorHeartbeatTimeoutMins`, `NetworkRerunHandoffRoot`, `WorkerCoordinatorUrl`, `WorkerName`, `WorkerPollIntervalSecs`, `WorkerSourcePathMap`, `WorkerConfigOverrides` | Non-secret network role/coordinator/worker settings |

---

## Known Advanced / Direct-Config Metadata

These keys are valid backend metadata and config-contract keys, but they do not have routine structured WebView builder controls. They are not schema drift. Use raw JSON/direct config plus backend Preview Patch before Save, and review the owning page before relying on changed behavior.

| Key | Category | Why no routine builder |
|---|---|---|
| `ConfigSchemaVersion` | Runtime / migration | Backend schema marker; editing is migration work |
| `MaxParallelEncodes` | Runtime / parallelism | Local parallel encode capacity needs deliberate validation |
| `ParallelEncodeMode` | Runtime / parallelism | Coupled to `MaxParallelEncodes` and local worker-slot validation |
| `MixPriorityPhase` | Queue planning | Advanced queue phase behavior; inspect Queue preview after changes |
| `QueueOrderingStrategy` | Queue planning | Backend queue sort preset; inspect Queue preview after changes |
| `FinalLibraryPromotionEnabled` | Final library promotion | Manual promotion workflow enable flag; review Completed/Output promotion workflow before use |
| `FinalLibraryPromotionRules` | Final library promotion | Source-to-final-library mapping; wrong roots can promote to the wrong final destination |
| `FinalLibraryPromotionVerificationMode` | Final library promotion | Promotion verification strictness; cautious hashes, fast checks size/existence |
| `FinalLibraryPromotionCleanupAfterVerified` | Final library promotion | Removes verified publish-output files after promotion; review cleanup boundary first |
| `FinalLibraryPromotionOverwriteExisting` | Final library promotion | Allows staged replacement of existing final files; high-impact publish behavior |
| `RenameMovieFilterOptions` | Rename planning | Movie rename cleaning options; inspect Rename preview before applying |
| `RenameMovieFilterTerms` | Rename planning | Movie rename term filters; inspect Rename preview before applying |
| `RenameMovieRemoveTerms` | Rename planning | Movie rename removal terms; inspect Rename preview before applying |
| `OutputValidationProbeTimeoutSeconds` | Output validation | Advanced completed-output validation threshold |
| `OutputValidationMinSizeBytes` | Output validation | Advanced completed-output acceptance threshold |
| `OutputValidationDurationToleranceSeconds` | Output validation | Advanced completed-output duration tolerance |
| `ConsecutiveRoundFailureBlockLimit` | Long-run reliability | Backend continuous-mode watchdog threshold; read-only evidence is shown in Diagnostics/Home |
| `ConsecutiveRoundFailureProbeBackoffSeconds` | Long-run reliability | Backend continuous-mode recovery-probe cadence; read-only evidence is shown in Diagnostics/Home |
| `PendingPublishBacklogBlockThreshold` | Pending publish backpressure | Backend queue-work backpressure threshold; not a frontend drain policy |
| `PendingPublishDeferredBlockThreshold` | Pending publish backpressure | Backend deferred-publish backpressure threshold; pending publish remains manifest-backed |
| `PauseFlagReviewSeconds` | Runtime control flags | Backend health age threshold; runtime pause flags are never auto-cleared |
| `PauseFlagBlockSeconds` | Runtime control flags | Backend health block threshold; runtime pause flags are never auto-cleared |
| `LocalWorkerHeartbeatGraceSeconds` | Local worker lifecycle | Backend worker-slot stale-heartbeat grace; no frontend claim release policy |
| `QueueExecutionMaxRunnablePerRound` | Queue planning | Backend per-round execution cap; queue snapshot display cap remains separate |
| `StateDbMaintenanceIntervalSeconds` | SQLite mirror observability | Backend best-effort mirror maintenance interval; JSON state remains authoritative |
| `StateDbWalReviewBytes` | SQLite mirror observability | Backend WAL review/maintenance threshold; JSON state remains authoritative |
| `StateDbCompletedJobsMaxRows` | SQLite mirror observability | Completed-job mirror row bound; JSONL completed manifests remain authoritative |
| `AutonomyPendingReviewSeconds` | Autonomy diagnostics policy | Backend-only pending-publish review threshold; no Settings builder control in this pass |
| `AutonomyPendingBlockSeconds` | Autonomy diagnostics policy | Backend-only pending-publish block threshold; pending publish remains manifest-backed |
| `AutonomyPendingRetryBlockCount` | Autonomy diagnostics policy | Backend-only pending-publish retry threshold; no frontend drain policy |
| `AutonomyPendingTotalReviewBytes` | Autonomy diagnostics policy | Publish & Recovery builder GiB control for pending-publish review evidence |
| `AutonomyPendingTotalBlockBytes` | Autonomy diagnostics policy | Publish & Recovery builder GiB control for pending-publish launch blocking |
| `AutonomyFailureOperatorRequiredBlockSeconds` | Autonomy diagnostics policy | Backend-only failure age block threshold |
| `AutonomyFailureOperatorRequiredBlockCount` | Autonomy diagnostics policy | Backend-only failure count block threshold |
| `AutonomyFailureInfrastructureBlockCount` | Autonomy diagnostics policy | Backend-only infrastructure failure count block threshold |
| `AutonomyActiveJobTimeoutGraceSeconds` | Autonomy diagnostics policy | Backend-only passive ActiveJobs stale grace; review-only liveness evidence |
| `AutonomyActiveJobNoTimeoutBlockSeconds` | Autonomy diagnostics policy | Backend-only passive ActiveJobs stale threshold without native timeout |
| `AutonomyStorageMinFreeGB` | Autonomy diagnostics policy | Backend-only storage floor for diagnostics budget evidence |
| `AutonomyStateFileReviewBytes` | Autonomy diagnostics policy | Backend-only state/journal file review threshold |
| `AutonomyStateFileBlockBytes` | Autonomy diagnostics policy | Backend-only state/journal file block threshold |
| `AutonomyScanLimit` | Autonomy diagnostics policy | Backend-only file enumeration cap with truncation metadata |
| `AutonomyGrowthSnapshotMaxCount` | Autonomy diagnostics policy | Backend-only retained growth snapshot count |
| `AutonomyWatchdogRecordLimit` | Autonomy diagnostics policy | Backend-only returned passive watchdog record cap |
| `ShowOverrides` | Per-show media policy | Direct-config mapping for show-specific routing/video/audio/subtitle overrides |

`LibraryProfiles` is handled by the dedicated Library Profiles editor rather than the static builder arrays.

---

## Intentionally Hidden From WebView

| Key | Category | Impact | Reason raw-only |
|---|---|---|---|
| `CoordinatorAuthToken` | Network | High | Auth secret — intentionally excluded from WebView builder |
| `WorkerAuthToken` | Network | High | Auth secret — intentionally excluded from WebView builder |

Auth tokens are intentionally hidden — they must not be added to the WebView builder without a design that prevents them from appearing in browser storage, dev tools, or JS heap snapshots.

---

## High-Impact OCR Path Fields

The fields most likely to cause operator confusion or silent failures if misconfigured are now covered by the Subtitle builder, while saved path resolution remains backend-authored:

| Key | Risk if misconfigured |
|---|---|
| `BdpgsOcrToolPath` | BDPGS OCR silently fails or uses wrong tool if path is stale or wrong |
| `BdpgsOcrTessdataPath` | OCR produces garbage or silently skips if data path is wrong |

**Implemented builder and read-only evidence**: WebView Settings now stages `BdpgsOcrToolPath` and `BdpgsOcrTessdataPath` through the Subtitle builder as text values. Backend Preview/Save remains the only persistence boundary. The backend resolves the saved paths against the pipeline script folder, reports tool/tessdata existence and `.dll`/`dotnet` posture, and marks missing enabled OCR paths as blocked. There is still no WebView path picker and no frontend-owned path resolution.

**Implemented action-plan display**: WebView Settings now also includes a read-only Raw-Key Action Plan. It groups unknown schema-drift keys, BDPGS OCR path evidence, subtitle keyword builder coverage, intentionally excluded auth secrets, remaining advanced raw keys, and the backend-owned mutation boundary so the operator sees which raw-key categories need action without adding new settings mutation.

---

## Coverage Notes

- Several keys appear in multiple builders (e.g., `DeferredPublish`, `CleanupRemoteStaging`, `RobocopyFlags`, `RobocopyTimeoutSeconds`, `OutsourceMinFreeSpaceGB`, `OutputSizeMultiplier`, `EnableIntegrityCheck`, `SkipStabilityCheck` appear in both File Safety and Pending Publish builders). This is by design — both pages have different operator workflows for the same underlying config key.
- The `ExtraVideoFlags` field is covered by the Video Detail builder but flagged as high-risk (raw FFmpeg passthrough) in both the local save-readiness checklist and backend risk policy.
- The `AllowNoAudio` field is covered by the Audio builder and explicitly flagged in risk policy as unsafe if the operator has no-audio output as the intended behavior.
- The `ReprocessAll` field is covered by the Queue builder but blocked by the local save-readiness checklist pending operator confirmation.

---

## Freshness Review — 2026-05-15 (CLN3-025)

Re-checked builder groups against current `settingsView.js` and `settingsOverview.js` to confirm no new fields were added or dropped.

| Builder | Status |
|---|---|
| Routing / Size | Pass — route, threshold mode, size, encode ladder, and movie/TV bitrate ceiling fields are builder-covered |
| Audio | Pass — `AudioPassthroughProfile`, passthrough/transcode/channel/language fields unchanged |
| Subtitle | Pass — TX3G, BDPGS, ASS/SSA convert/drop/preserve fields covered; `AllowSubtitleHelperFallback` is represented as a launch-safety setting with backend-owned behavior |
| Pending Publish / Recovery | Pass — `DeferredPublish`, `PendingPublishDrainMode`, `PendingPublishDrainBatchSize`, `RobocopyFlags`, and `CleanupStaleAgeHours` covered |
| Auth token exclusion | Pass — `CoordinatorAuthToken` / `WorkerAuthToken` still intentionally raw-only |
| New sample-validation config keys | None — sample validation is not a settings/config concern; its limits are constants in `app/sample_validation/policy.py` |

No builder coverage gaps introduced. `BdpgsOcrToolPath` / `BdpgsOcrTessdataPath` raw-only recommendation closed by the Subtitle builder text fields; `SubSDHTitleKeywords` / `SubSupplementalKeywords` are now list fields staged through the same backend Preview/Save flow. No path picker was added, and auth tokens remain intentionally excluded.

```
Task ID: CLN3-025
Files inspected: docs\inventories\SETTINGS_BUILDER_COVERAGE_MATRIX.md, docs\inventories\SETTINGS_KEY_OWNERSHIP_MAP.md (reference), docs\architecture\SETTINGS_RAW_KEY_TRIAGE.md (reference)
Files changed: docs\inventories\SETTINGS_BUILDER_COVERAGE_MATRIX.md (CLN3-025 freshness note added)
Validation: Select-String -Path docs\inventories\SETTINGS_BUILDER_COVERAGE_MATRIX.md,docs\inventories\SETTINGS_KEY_OWNERSHIP_MAP.md,docs\architecture\SETTINGS_RAW_KEY_TRIAGE.md -Pattern "audio|subtitle|pending|raw-only|builder"
Findings: All builder groups current. No new fields added or dropped.
Open questions: None.
Risk: Low — documentation only.
```
