# ==============================================================================
# MEDIA PIPELINE v1.0
# ==============================================================================
# Release 1.0 — consolidated stability, operator-control, and observability improvements
# (All tagged [FIX#N] reference the v7.8.1 consolidated code-review findings.)
#
#  [FIX#1]  Ensure-ScratchCopy no longer reuses scratch files by filename
#           alone. A `.srcinfo` fingerprint sidecar (source full path +
#           size + last-write time) is written next to every scratch copy
#           and verified on reuse. Different source files that sanitise
#           to the same safe-name (e.g. "Episode 01.mkv" from two shows)
#           are now copied independently and never cross-contaminate.
#
#  [FIX#2]  Disk-space checks now work on UNC paths. Test-DiskSpace and
#           Get-FreeSpaceGB were silently returning "enough space" for
#           anything starting with \\server\share, allowing the outsource
#           to fill up and corrupt mid-copy. Replaced with a P/Invoke
#           wrapper around kernel32!GetDiskFreeSpaceExW which works for
#           drive letters AND UNC paths. Also added a pre-push disk-
#           space probe on the outsource share.
#
#  [FIX#5]  Auto-disable of ReprocessAll after one complete pass. Leaving
#           ReprocessAll=$true in config used to re-encode the whole
#           library every 30 s forever. The pipeline now flips the flag
#           off in-memory after one full round and logs a loud warning
#           telling the operator to disable it in config.
#
#  [FIX#6]  Robocopy now copies to <dest>.mp-partial and atomically
#           renames on success. Mid-copy failures no longer leave a
#           truncated MKV at the final path that future runs "find"
#           and skip. Any orphan .mp-partial files from previous failed
#           runs are cleaned at startup.
#
#  [FIX#8]  Normalize-MovieName is now a thin wrapper around
#           Get-CleanMovieName. The divergent cleaning rules that caused
#           Build-ProcessedIndex keys to never match the output folder
#           names are gone. Already-Processed also has a direct
#           Test-Path fallback for movies, so even when the index is
#           stale or empty the reprocess-check still works.
#
#  [FIX#9]  Outsource index scan no longer has a 120 s hard timeout
#           that would silently return an empty index on large libraries
#           (causing all reprocessing to be skipped). New optional
#           config key IndexScanTimeoutSeconds; default 1800s.
#
#  [FIX#10] Successful encodes are no longer deleted by the finally
#           block when the server push fails. The output is preserved
#           in LocalBase\PendingServerPush\ with a timestamp, and is
#           pushed to the outsource at the start of the next run.
#           Hours of encode time on a flaky network are no longer lost.
#
#  [FIX#11] Write-Sidecar now retries up to 3x and returns $true/$false.
#           Callers treat a persistent sidecar write failure as a real
#           failure — the outsource file is removed so next run
#           regenerates it cleanly instead of looping re-encode forever.
#
#  [FIX#13] ConvertTo-Milliseconds accepts 1-3 digit millisecond fields.
#           "00:00:12,1" and "00:00:12,01" now parse correctly instead
#           of silently returning 0 (which caused spurious merges).
#
#  [NEW]    PendingServerPush\ scan at startup. Any .mkv found there
#           is pushed to the outsource before normal processing
#           resumes, so a network hiccup on one run gets fixed on
#           the next run with zero operator intervention.
#
#  [NEW]    Config key IncludeSubtitleStyles — a whitelist of ASS
#           style-name glob patterns that are ALWAYS kept, even if they
#           also match ExcludeSubtitleStyles. Defends against fansubs
#           that mislabel dialogue with a "Sign" or "Caption" style.
#
# ==============================================================================
# MEDIA PIPELINE v7.8.1
# ==============================================================================
# Changes from v7.8.0:
#
#  [NEW]  Plex-style movie folders. Every movie output now goes into its
#         own folder named "Title (Year)", matching the movie file itself:
#             Outsource\Avatar (2009)\Avatar (2009).mkv
#             Outsource\Avatar (2009)\Avatar (2009).pipeline.json
#         This is Plex's preferred layout (one folder per movie entry)
#         and keeps sidecars, subtitle files, posters, etc. grouped with
#         the movie they belong to.
#
#         TV files are unaffected — they continue to use
#         TV\<Show>\Season NN\<Show> - SxxEyy.mkv.
#
#         Title parsing strips bracketed text ({}, [], ()) and common
#         release tags (UHD, HDR, 1080p, etc.). Prefers bracketed years
#         over unbracketed ones to avoid misparsing titles like
#         "Blade Runner 2049 (2017)". See Get-CleanMovieName docstring.
#
#  [FIX]  Case-insensitive variable collision in Build-AudioArgs. The
#         loop-local $langDisplay was rebinding the outer $LangDisplay
#         hashtable, causing the second audio track to fail with "String
#         does not contain a method named ContainsKey". Renamed to
#         $langDisp. Same defensive fix in Filter-SubtitleStreams.
#
# ==============================================================================
# MEDIA PIPELINE v7.8.0
# ==============================================================================
# Changes from v7.7.0:
#
#  [NEW]  Per-show configuration overrides. Config key `ShowOverrides` is a
#         hashtable keyed by glob pattern (case-insensitive). When a TV
#         show matches, the override's keys replace the global defaults for
#         that file. Supported overrides: DropAssAfterConversion,
#         DropTx3gAfterConversion, DropBdpgsAfterConversion,
#         CompatibleAudioCodecs, RemoveKaraoke,
#         KeepSignsAndSongs, TreatAssSignsSongsAsForced,
#         TreatTx3gSignsSongsAsForced, TreatBdpgsSignsSongsAsForced,
#         ExcludeSubtitleStyles, FlacAsCompatible. Applied at the start of
#         Process-File for TV content.
#
#  [NEW]  Reprocess-on-version tracking. Each successful output writes a
#         `.pipeline.json` sidecar with pipeline version, timestamp, and
#         a quick summary. On the next run, any file whose sidecar version
#         is older than `MinPipelineVersion` (config) is reprocessed even
#         if its filename already exists on the outsource. Also added
#         `ReprocessAll` config toggle — when true, ignores all sidecars
#         for one run (good for testing changes).
#
#  [NEW]  Global title metadata. Output MKVs now include a global `title`
#         tag "Encoded by MediaPipeline vX.Y.Z" for long-term traceability.
#
#  [NEW]  Output summary log line after every successful encode/remux.
#         One line lists size, video codec+resolution, audio tracks
#         (lang/channels/codec/default), and subtitle tracks (lang/codec/
#         default/forced). Makes log review dramatically easier.
#
#  [NEW]  Pre-encode disk space check. Estimates output size at
#         sourceSize * OutputSizeMultiplier (default 0.7) and skips
#         with a clear "insufficient space for estimated output" log
#         instead of failing mid-encode.
#
#  [NEW]  Post-encode duration sanity check. Compares source and output
#         durations; if they differ by more than 1 second the output is
#         treated as corrupt (moved to Failed/). Catches silent truncations
#         where ffmpeg exits 0 but produced a short file.
#
#  [NEW]  NVENC fallback to libx265. When an encode fails with symptoms
#         of NVENC session/driver trouble (session init failure, OOM,
#         driver error), the pipeline automatically retries once with
#         CPU libx265. CQ value configurable via `FallbackCpuQuality`
#         (default 20). Encoded file is marked `[CPU]` in the summary.
#
#  [DOC]  Subtitle forced-track disposition was already being written
#         correctly in both mkvmerge (--forced-track) and ffmpeg
#         (-disposition:s:N default+forced) paths as of v7.6.0 — this
#         changelog entry documents it for clarity. No code change.
#
#  [NEW]  Explicit audio channel layout tagging on copy operations.
#         Emits `-channel_layout:a:N <layout>` based on source channel
#         count to prevent ambiguous 5.1 vs 5.1(side) metadata that
#         confuses some receivers.
#
#  [NEW]  TV filename sanitization improvements:
#         ①  Trailing separator cleanup — show names extracted via SxxExx /
#             NxM no longer carry a trailing " - " or "_" when the filename
#             format is "Show Name - S01E01 - Title".
#         ②  Year token preservation — "(2024)" and "(2005)" are saved and
#             re-appended after bracket-stripping so remakes/reboots keep
#             their year in the output name (e.g. "Shogun (2024)").
#         ③  ShowName key in ShowOverrides — config entries can now include
#             ShowName = "Canonical Title" to canonicalize alternate-title or
#             fansub-named shows. Applied before Already-Processed so the
#             index key and output path are consistent from the first run.
#         ④  Multi-episode support — SxxExx files with two-part notation
#             (S01E01E02 / S01E01-E02 / S01E01_E02) produce a ranged output
#             filename "Show - S01E01-E02 - Title.mkv". The processed index
#             keys every episode in the span so neither half is reprocessed.
#         ⑤  Fansub pre-SxxExx episode title extraction — Get-EpisodeTitle
#             now detects titles that appear BEFORE the SxxExx marker
#             ("[Group] Show - Title - S01E01 [tags]") in addition to the
#             standard post-marker layout.
#         ⑥  Get-QueueEpisodeNumber extended — sort key for fansub files that
#             use "Episode N", "Ep N", or a bare trailing number is now
#             populated, so they queue in episode order instead of filename
#             alphabetical order.
#         ⑦  Normalize-TVShowFolderName strips bare trailing "S02" season
#             markers in addition to the existing "(Season 2)" / "(S02)" forms.
# ==============================================================================

[CmdletBinding()]
param(
    [switch]$Once,
    [switch]$DrainPendingPushes,
    [switch]$ValidateOnly,
    [switch]$ShowConfig,
    [string]$ConfigPath,
    [ValidateRange(1, 86400)]
    [int]$SleepSeconds = 30,

    # Dry-run: build the same queue the live pipeline would, run all the
    # same Already-Processed / pending-publish / sidecar-version filters,
    # write the resulting ordered plan as JSON, and exit before processing
    # any file. Used by the desktop app's Queue tab so the preview matches
    # the actual run order with no second source of truth.
    [switch]$EmitQueuePlan,
    [string]$QueuePlanOutPath,

    # Worker mode: skip queue discovery and encode exactly one file.
    # When non-empty, the pipeline builds a synthetic single-item plan
    # from this path, processes it, then exits.  The existing queue,
    # sidecar, and already-processed logic all still apply — the file
    # is skipped with a log message if it would ordinarily be skipped.
    # When empty (the default), behaviour is identical to today.
    [string]$SingleFile = "",

    # Local worker-slot child mode. Child processes skip the controller mutex
    # and take a slot-specific mutex while processing one claimed file.
    [switch]$WorkerChild,
    [int]$WorkerSlotId = 0,
    [string]$WorkerRunId = "",
    [string]$WorkerClaimId = "",
    [string]$WorkerResultPath = ""
)

if ($PSVersionTable.PSVersion.Major -lt 7) {
    Write-Host "This script requires PowerShell 7 or higher." -ForegroundColor Red
    Write-Host "Current version: $($PSVersionTable.PSVersion)" -ForegroundColor Yellow
    Write-Host "Attempting to relaunch with PowerShell 7..." -ForegroundColor Yellow
    $scriptPath = $MyInvocation.MyCommand.Path
    $scriptDir = if ($PSScriptRoot) {
        $PSScriptRoot
    } elseif ($scriptPath) {
        Split-Path -Parent $scriptPath
    } else {
        (Get-Location).Path
    }

    $pwshCandidates = [System.Collections.Generic.List[string]]::new()
    foreach ($candidate in @(
            (Join-Path $scriptDir 'pwsh.exe'),
            (Join-Path $scriptDir 'PowerShell-7.6.0-win-x64\pwsh.exe')
        )) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            [void]$pwshCandidates.Add($candidate)
        }
    }
    Get-ChildItem -LiteralPath $scriptDir -Directory -Filter 'PowerShell-*' -ErrorAction SilentlyContinue |
        ForEach-Object {
            $candidate = Join-Path $_.FullName 'pwsh.exe'
            if (Test-Path -LiteralPath $candidate) {
                [void]$pwshCandidates.Add($candidate)
            }
        }

    $pwshCommand = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($pwshCommand -and $pwshCommand.Source) {
        [void]$pwshCandidates.Add($pwshCommand.Source)
    }

    $pwshPath = $pwshCandidates | Select-Object -Unique | Select-Object -First 1
    if (-not $pwshPath) {
        Write-Host "ERROR: PowerShell 7 was not found next to the script or on PATH." -ForegroundColor Red
        Write-Host "Checked for bundled pwsh.exe under: $scriptDir" -ForegroundColor Yellow
        Write-Host "Install from https://aka.ms/ps7 or ship a PowerShell-7.x folder with the deployment bundle." -ForegroundColor Yellow
        exit 1
    }

    $relaunchArgs = @('-File', $scriptPath)
    foreach ($entry in $PSBoundParameters.GetEnumerator()) {
        $name = "-$($entry.Key)"
        if ($entry.Value -is [switch]) {
            if ($entry.Value.IsPresent) { $relaunchArgs += $name }
            continue
        }
        if ($entry.Value -is [bool]) {
            if ($entry.Value) { $relaunchArgs += $name }
            continue
        }
        $relaunchArgs += $name
        $relaunchArgs += [string]$entry.Value
    }
    if ($args.Count -gt 0) {
        $relaunchArgs += $args
    }

    & $pwshPath @relaunchArgs
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

# ==============================================================================
# MODULE LOADING (dot-source)
# ------------------------------------------------------------------------------
# Pure-function and shared-state helpers live in engine\<domain>\*.ps1 and are
# dot-sourced through compatibility loaders so they share this script's scope.
# This keeps `$script:*` semantics intact —
# extraction is purely a code-locality change with no behavioural impact.
#
# Order matters slightly:
#   - Logging.ps1 defines Add-StartupWarning (called by the config-loader
#     helpers below), so it must be sourced first.
#   - PathHelpers.ps1 must come before Native.ps1 (Save-ReproCommand and
#     Invoke-RecursivePathScan reference Format-NativeCommandLine and
#     Test-IsUncPath at definition time? No — at call time. Listed first
#     anyway for readability of the dependency chain.)
#   - MediaConstants.ps1 owns shared route/codec/container names used by
#     routing, encode policy, probes, audio, subtitle, and failure helpers.
#   - FailureCodes.ps1, ConfigSchema.ps1, Routing.ps1, and EncodePolicy.ps1
#     are pure and mostly order-independent after constants are loaded.
#   - Native.ps1 references Write-Log/DebugLog (Logging) and
#     Format-NativeCommandLine/Test-IsUncPath (PathHelpers) at CALL time, so
#     it just needs both loaded before the main loop runs.
#   - NativeProcessContracts.ps1 loads before Native.ps1 and
#     FfmpegProgress.ps1 so all native runners share result metadata,
#     callback-safe stream draining, and timeout policy.
#   - Disk.ps1 loads after Native.ps1 because the robocopy helper uses the
#     bounded native-command runner and stop-aware sleep helper.
#   - ProgressState.ps1 loads before PendingPush.ps1 so pending-push retry
#     helpers can report progress.
#   - FfmpegProgress.ps1 loads after ProgressState.ps1 because the progress-aware
#     ffmpeg runner updates stage progress while it runs.
#   - PendingManifestStore.ps1 loads before PendingTransactions.ps1 and
#     PendingPush.ps1 so manifest read, write, validation, and retry-state
#     persistence stay isolated from the park/drain state machine.
#   - PendingTransactions.ps1 loads before PendingPush.ps1 so durable
#     pending-push park transactions stay isolated from operator-facing
#     logging, event emission, and drain/retry orchestration.
#   - PendingPublishIndex.ps1 loads after PendingPush.ps1 so index refresh can
#     call the existing pending_move repair helper without changing recovery
#     semantics.
#   - PublishCompletion.ps1 loads after PendingPush.ps1 because completed
#     output publish orchestration parks retry/deferred outputs.
# ==============================================================================
$pipelineRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$repoRootForModules = Split-Path -Parent $pipelineRoot
$moduleRoot = Join-Path $pipelineRoot 'Modules'
$engineModulePaths = @{
    'Audio.ps1'                 = Join-Path $repoRootForModules 'engine\audio\audio.ps1'
    'Logging.ps1'               = Join-Path $repoRootForModules 'engine\observability\logging.ps1'
    'ConfigGetters.ps1'          = Join-Path $repoRootForModules 'engine\config\getters.ps1'
    'ConfigKeys.ps1'             = Join-Path $repoRootForModules 'engine\config\config_keys.ps1'
    'ConfigSchema.ps1'           = Join-Path $repoRootForModules 'engine\config\config_schema.ps1'
    'Disk.ps1'                   = Join-Path $repoRootForModules 'engine\storage\disk.ps1'
    'EncodePolicy.ps1'           = Join-Path $repoRootForModules 'engine\decide\encode_policy.ps1'
    'ExecutableResolution.ps1'   = Join-Path $repoRootForModules 'engine\shared\executable_resolution.ps1'
    'FailureCodes.ps1'           = Join-Path $repoRootForModules 'engine\shared\failure_codes.ps1'
    'FailureState.ps1'           = Join-Path $repoRootForModules 'engine\failures\failure_state.ps1'
    'FfmpegProgress.ps1'         = Join-Path $repoRootForModules 'engine\process\ffmpeg_progress.ps1'
    'FileOverrides.ps1'          = Join-Path $repoRootForModules 'engine\queue\file_overrides.ps1'
    'FolderPolicy.ps1'           = Join-Path $repoRootForModules 'engine\policy\folder_policy.ps1'
    'LibraryIndex.ps1'           = Join-Path $repoRootForModules 'engine\library\library_index.ps1'
    'LocalWorkerSlots.ps1'       = Join-Path $repoRootForModules 'engine\queue\local_worker_slots.ps1'
    'MediaConstants.ps1'         = Join-Path $repoRootForModules 'engine\shared\media_constants.ps1'
    'MediaProbe.ps1'             = Join-Path $repoRootForModules 'engine\probe\media_probe.ps1'
    'Naming.ps1'                 = Join-Path $repoRootForModules 'engine\naming\naming.ps1'
    'Native.ps1'                 = Join-Path $repoRootForModules 'engine\shared\native.ps1'
    'NativeProcessContracts.ps1' = Join-Path $repoRootForModules 'engine\shared\native_process_contracts.ps1'
    'OutputPathPlanning.ps1'     = Join-Path $repoRootForModules 'engine\paths\output_path_planning.ps1'
    'PathHelpers.ps1'            = Join-Path $repoRootForModules 'engine\shared\path_helpers.ps1'
    'PendingManifestStore.ps1'   = Join-Path $repoRootForModules 'engine\publish\pending_manifest_store.ps1'
    'PendingPublishIndex.ps1'    = Join-Path $repoRootForModules 'engine\publish\pending_publish_index.ps1'
    'PendingPush.ps1'            = Join-Path $repoRootForModules 'engine\publish\pending_push.ps1'
    'PendingTransactions.ps1'    = Join-Path $repoRootForModules 'engine\publish\pending_transactions.ps1'
    'PipelineEngine.ps1'         = Join-Path $repoRootForModules 'engine\queue\pipeline_engine.ps1'
    'PipelineProcessing.ps1'     = Join-Path $repoRootForModules 'engine\process\pipeline_processing.ps1'
    'ProgressState.ps1'          = Join-Path $repoRootForModules 'engine\status\progress_state.ps1'
    'Publish.Partial.ps1'        = Join-Path $repoRootForModules 'engine\publish\publish_partial.ps1'
    'Publish.Result.ps1'         = Join-Path $repoRootForModules 'engine\publish\publish_result.ps1'
    'Publish.Sidecars.ps1'       = Join-Path $repoRootForModules 'engine\publish\publish_sidecars.ps1'
    'PublishCompletion.ps1'      = Join-Path $repoRootForModules 'engine\publish\publish_completion.ps1'
    'QueuePlan.ps1'              = Join-Path $repoRootForModules 'engine\queue\queue_plan.ps1'
    'Routing.ps1'                = Join-Path $repoRootForModules 'engine\decide\routing.ps1'
    'ScratchCopy.ps1'            = Join-Path $repoRootForModules 'engine\storage\scratch_copy.ps1'
    'ShowOverrides.ps1'          = Join-Path $repoRootForModules 'engine\decide\show_overrides.ps1'
    'Sidecar.ps1'                = Join-Path $repoRootForModules 'engine\publish\sidecar.ps1'
    'SourceIdentity.ps1'         = Join-Path $repoRootForModules 'engine\shared\source_identity.ps1'
    'StateStore.ps1'             = Join-Path $repoRootForModules 'engine\storage\state_store.ps1'
    'Subtitles.ps1'              = Join-Path $repoRootForModules 'engine\subtitles\subtitles.ps1'
    'TempCleanup.ps1'            = Join-Path $repoRootForModules 'engine\shared\temp_cleanup.ps1'
    'Versioning.ps1'             = Join-Path $repoRootForModules 'engine\shared\versioning.ps1'
}
foreach ($module in @('Logging.ps1', 'ConfigGetters.ps1', 'ConfigKeys.ps1', 'ExecutableResolution.ps1', 'TempCleanup.ps1', 'PathHelpers.ps1', 'MediaConstants.ps1', 'ShowOverrides.ps1', 'Versioning.ps1', 'FailureCodes.ps1', 'ConfigSchema.ps1', 'StateStore.ps1', 'Routing.ps1', 'EncodePolicy.ps1', 'NativeProcessContracts.ps1', 'Native.ps1', 'Disk.ps1', 'MediaProbe.ps1', 'FolderPolicy.ps1', 'FileOverrides.ps1', 'Audio.ps1', 'Subtitles.ps1', 'ProgressState.ps1', 'FfmpegProgress.ps1', 'QueuePlan.ps1', 'Naming.ps1', 'OutputPathPlanning.ps1', 'SourceIdentity.ps1', 'ScratchCopy.ps1', 'LocalWorkerSlots.ps1', 'FailureState.ps1', 'Sidecar.ps1', 'Publish.Result.ps1', 'Publish.Partial.ps1', 'Publish.Sidecars.ps1', 'PendingManifestStore.ps1', 'PendingTransactions.ps1', 'PendingPush.ps1', 'PendingPublishIndex.ps1', 'PublishCompletion.ps1', 'LibraryIndex.ps1', 'PipelineProcessing.ps1', 'PipelineEngine.ps1')) {
    $modulePath = if ($engineModulePaths.ContainsKey($module)) { $engineModulePaths[$module] } else { Join-Path $moduleRoot $module }
    if (-not (Test-Path -LiteralPath $modulePath)) {
        Write-Host "FATAL: required module not found: $modulePath" -ForegroundColor Red
        exit 1
    }
    . $modulePath
}

# ==============================================================================
# CONFIGURATION
# ==============================================================================
$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$configCandidates = if ($ConfigPath) {
    $candidate = if ([System.IO.Path]::IsPathRooted($ConfigPath)) {
        $ConfigPath
    } else {
        Join-Path (Get-Location).Path $ConfigPath
    }
    @($candidate)
} else {
    @(
        (Join-Path $scriptRoot "MediaPipeline_config_chatgpt.psd1"),
        (Join-Path $scriptRoot "MediaPipeline_config.psd1")
    )
}
$configPath = $configCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $configPath) {
    Write-Host "ERROR: Config not found. Checked: $($configCandidates -join ', ')" -ForegroundColor Red; exit 1
}
$configPath = (Resolve-Path -LiteralPath $configPath).Path
$config = Import-PowerShellDataFile $configPath

$configSchemaCheck = Test-MediaPipelineConfigSchema -Config $config
if (-not $configSchemaCheck.Ok) {
    foreach ($errorText in @($configSchemaCheck.Errors)) {
        Write-Host "ERROR: $errorText" -ForegroundColor Red
    }
    exit 1
}
foreach ($warningText in @($configSchemaCheck.Warnings)) {
    Add-StartupWarning $warningText
}
$requiredKeys = @($configSchemaCheck.RequiredKeys)
$arrayKeys = @($configSchemaCheck.ArrayKeys)
$script:ConfigSchemaVersion = [int]$configSchemaCheck.EffectiveSchemaVersion

foreach ($key in $config.Keys) {
    $value = $config[$key]
    if ($key -in $arrayKeys) {
        if ($null -eq $value)          { $value = @() }
        elseif ($value -isnot [array]) { $value = @($value) }
    }
    Set-Variable -Name $key -Value $value -Scope Script
}
$script:ConfigSchemaVersion = [int]$configSchemaCheck.EffectiveSchemaVersion
if (-not (Get-Variable -Name ExtraVideoFlags -Scope Script -ErrorAction SilentlyContinue)) {
    $script:ExtraVideoFlags = @()
}

$script:StripFormatting   = Get-ConfigBool 'StripFormatting'   $true
$script:MergeAdjacent     = Get-ConfigBool 'MergeAdjacent'     $true
$script:RemoveKaraoke     = Get-ConfigBool 'RemoveKaraoke'     $true
$script:KeepSignsAndSongs = Get-ConfigBool 'KeepSignsAndSongs' $true
$script:ConvertTx3gToSrt  = Get-ConfigBool 'ConvertTx3gToSrt'  $true
$script:DropTx3gAfterConversion = Get-ConfigBool 'DropTx3gAfterConversion' $false
$script:CreateExternalTx3gSrtSidecars = Get-ConfigBool 'CreateExternalTx3gSrtSidecars' $false
$script:Tx3gPreserveExistingSrt = Get-ConfigBool 'Tx3gPreserveExistingSrt' $true
$script:Tx3gTreatForcedAsSeparate = Get-ConfigBool 'Tx3gTreatForcedAsSeparate' $true
$script:ConvertBdpgsToSrt = Get-ConfigBool 'ConvertBdpgsToSrt' $false
$script:DropBdpgsAfterConversion = Get-ConfigBool 'DropBdpgsAfterConversion' $false
$script:TreatBdpgsSignsSongsAsForced = Get-ConfigBool 'TreatBdpgsSignsSongsAsForced' $false
$script:BdpgsOcrToolPath = if ($config.ContainsKey('BdpgsOcrToolPath')) { [string]$config['BdpgsOcrToolPath'] } else { '' }
$script:BdpgsOcrTessdataPath = if ($config.ContainsKey('BdpgsOcrTessdataPath')) { [string]$config['BdpgsOcrTessdataPath'] } else { '' }
$script:TreatAssSignsSongsAsForced = Get-ConfigBool 'TreatAssSignsSongsAsForced' $false
$script:TreatTx3gSignsSongsAsForced = Get-ConfigBool 'TreatTx3gSignsSongsAsForced' $false
$script:AggressiveEpisodeParsing = Get-ConfigBool 'AggressiveEpisodeParsing' $false
$script:AllowSystemTools = Get-ConfigBool 'AllowSystemTools' $false
$script:MergeThresholdMs  = Get-ConfigInt  'MergeThresholdMs'  150 0 5000
$script:LogRetentionDays  = Get-ConfigInt  'LogRetentionDays'  7   1 365
$script:FFmpegEncodeTimeoutSeconds = Get-ConfigInt 'FFmpegEncodeTimeoutSeconds' 21600 300 172800
# CPU encodes can be 5-15x slower than NVENC. A separate ceiling lets the GPU
# timeout stay tight without strangling a long-running libx265 fallback. If the
# operator did not set one, default to 2x the GPU timeout so old configs do not
# silently degrade.
$script:FFmpegCpuEncodeTimeoutSeconds = Get-ConfigInt 'FFmpegCpuEncodeTimeoutSeconds' ([int][math]::Min(172800, $script:FFmpegEncodeTimeoutSeconds * 2)) 300 172800
$script:FFmpegRemuxTimeoutSeconds  = Get-ConfigInt 'FFmpegRemuxTimeoutSeconds'  7200 300 86400
# R2 fix — replaces the previous hard-coded 600 s mkvmerge timeout in
# Do-Remux. mkvmerge default in Get-NativeToolDefaultTimeoutSeconds is
# 21600 s, so the old 600 was both inconsistent and far too short for
# 50 GB+ MKVs over slow scratch volumes.
$script:MkvmergeRemuxTimeoutSeconds = Get-ConfigInt 'MkvmergeRemuxTimeoutSeconds' 7200 60 86400
$script:SubtitleExtractTimeoutSeconds = Get-ConfigInt 'SubtitleExtractTimeoutSeconds' 180 30 3600
$script:SubtitleProbeTimeoutSeconds   = Get-ConfigInt 'SubtitleProbeTimeoutSeconds' 30 5 600
$script:BdpgsOcrTimeoutSeconds        = Get-ConfigInt 'BdpgsOcrTimeoutSeconds' 1800 60 14400
$script:SourceScanIntervalSeconds    = Get-ConfigInt 'SourceScanIntervalSeconds' 300 0 86400
$script:ProcessedIndexRefreshSeconds = Get-ConfigInt 'ProcessedIndexRefreshSeconds' 900 0 86400
$script:RobocopyTimeoutSeconds       = Get-ConfigInt 'RobocopyTimeoutSeconds' 14400 60 172800
$script:SourceScanTimeoutSeconds     = Get-ConfigInt 'SourceScanTimeoutSeconds' 1800 30 86400
$script:CleanupScanTimeoutSeconds    = Get-ConfigInt 'CleanupScanTimeoutSeconds' 300 30 7200
$script:CleanupRemoteStaging         = Get-ConfigBool 'CleanupRemoteStaging' $false
$script:CleanupStaleAgeHours         = Get-ConfigInt 'CleanupStaleAgeHours' 24 1 720
$script:TransientFailureRetryLimit   = Get-ConfigInt 'TransientFailureRetryLimit' 3 1 100

# v1.0 — new optional keys
#
# IndexScanTimeoutSeconds — hard cap on the outsource-index scan.
# 0 used to mean no timeout, but recursive SMB walks can block forever on
# offline shares/DFS targets. Treat 0 as the daily-use bounded default.
$script:IndexScanTimeoutSeconds = Get-ConfigInt 'IndexScanTimeoutSeconds' 1800 0 86400
if ($script:IndexScanTimeoutSeconds -le 0) {
    Add-StartupWarning "IndexScanTimeoutSeconds=0 is no longer supported for daily use; using 1800 seconds"
    $script:IndexScanTimeoutSeconds = 1800
}

# OutsourceMinFreeSpaceGB — minimum free space on the outsource share.
# Checked before every server push in Copy-FileRobocopy. Defaults to
# MinFreeSpaceGB if unset (so behaviour is unchanged for existing
# configs). Separate key exists because network shares typically have
# much larger capacity than the local scratch drive.
$script:OutsourceMinFreeSpaceGB = Get-ConfigInt 'OutsourceMinFreeSpaceGB' 0 0 1000000
if ($script:OutsourceMinFreeSpaceGB -le 0) {
    $script:OutsourceMinFreeSpaceGB = [int]$MinFreeSpaceGB
}

# ExcludeSubtitleStyles — list of shell-glob patterns (case-insensitive) that
# match non-dialogue ASS style names. Events whose Style matches any pattern
# are dropped before conversion. Empty list = use ass_to_srt.py built-in defaults.
if ($config.ContainsKey('ExcludeSubtitleStyles')) {
    $v = $config['ExcludeSubtitleStyles']
    if     ($null -eq $v)            { $script:ExcludeSubtitleStyles = @() }
    elseif ($v -isnot [array])       { $script:ExcludeSubtitleStyles = @($v) }
    else                              { $script:ExcludeSubtitleStyles = @($v) }
} else {
    $script:ExcludeSubtitleStyles = @()
}

# FIX#14 — IncludeSubtitleStyles (whitelist). Any ASS event whose Style
# matches one of these glob patterns is ALWAYS kept, even if it also
# matches ExcludeSubtitleStyles. Defends against fansubs that mislabel
# real dialogue with a non-dialogue style like "Sign" or "Caption".
# Empty list = no whitelist (backward-compatible).
if ($config.ContainsKey('IncludeSubtitleStyles')) {
    $v = $config['IncludeSubtitleStyles']
    if     ($null -eq $v)       { $script:IncludeSubtitleStyles = @() }
    elseif ($v -isnot [array])  { $script:IncludeSubtitleStyles = @($v) }
    else                         { $script:IncludeSubtitleStyles = @($v) }
} else {
    $script:IncludeSubtitleStyles = @()
}

if ($config.ContainsKey('Tx3gExtractLanguages')) {
    $v = $config['Tx3gExtractLanguages']
    if     ($null -eq $v)       { $script:Tx3gExtractLanguages = @() }
    elseif ($v -isnot [array])  { $script:Tx3gExtractLanguages = @($v) }
    else                         { $script:Tx3gExtractLanguages = @($v) }
} else {
    $script:Tx3gExtractLanguages = @($SubKeepLanguages)
}
$script:Tx3gExtractLanguages = @(
    $script:Tx3gExtractLanguages |
        ForEach-Object {
            $text = [string]$_
            if ([string]::IsNullOrWhiteSpace($text)) { 'und' } else { $text.Trim().ToLowerInvariant() }
        } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Select-Object -Unique
)
if ($script:Tx3gExtractLanguages.Count -eq 0) {
    $script:Tx3gExtractLanguages = @($SubKeepLanguages)
}

if ($config.ContainsKey('BdpgsExtractLanguages')) {
    $v = $config['BdpgsExtractLanguages']
    if     ($null -eq $v)       { $script:BdpgsExtractLanguages = @() }
    elseif ($v -isnot [array])  { $script:BdpgsExtractLanguages = @($v) }
    else                         { $script:BdpgsExtractLanguages = @($v) }
} else {
    $script:BdpgsExtractLanguages = @($SubKeepLanguages)
}
$script:BdpgsExtractLanguages = @(
    $script:BdpgsExtractLanguages |
        ForEach-Object {
            $text = [string]$_
            if ([string]::IsNullOrWhiteSpace($text)) { 'und' } else { $text.Trim().ToLowerInvariant() }
        } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Select-Object -Unique
)
if ($script:BdpgsExtractLanguages.Count -eq 0) {
    $script:BdpgsExtractLanguages = @($SubKeepLanguages)
}

if ($config.ContainsKey('PriorityMarkers')) {
    $v = $config['PriorityMarkers']
    if     ($null -eq $v)       { $script:PriorityMarkers = @() }
    elseif ($v -isnot [array])  { $script:PriorityMarkers = @($v) }
    else                         { $script:PriorityMarkers = @($v) }
} else {
    $script:PriorityMarkers = @('!', '[NOW]')
}
$script:PriorityMarkers = @(
    $script:PriorityMarkers |
        ForEach-Object { [string]$_ } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        ForEach-Object { $_.Trim() } |
        Select-Object -Unique
)
if ($script:PriorityMarkers.Count -eq 0) {
    $script:PriorityMarkers = @('!', '[NOW]')
}

# MixPriorityPhase — when $true, high-priority movies and high-priority TV
# are merged into a single phase (pre-manifest legacy behaviour).
# Default $false: separate phase-movie and phase-TV passes run in order.
$script:MixPriorityPhase = Get-ConfigBool 'MixPriorityPhase' $false

# QueueOrderingStrategy — config-file default for the queue sort preset.
# The DesktopApp UI can override this at runtime via queue_strategy.json.
# Valid values: Standard | FreshestFirst | ShowComplete | RoundRobin |
#               DeadlineAware | SmallFirst | LargeFirst | ManualOrder
$script:QueueOrderingStrategy = if ($config.ContainsKey('QueueOrderingStrategy')) {
    $v = [string]$config['QueueOrderingStrategy']
    $validStrats = @('Standard','FreshestFirst','ShowComplete','RoundRobin','DeadlineAware','SmallFirst','LargeFirst','ManualOrder')
    if ($v -in $validStrats) { $v } else { 'Standard' }
} else { 'Standard' }

$script:MaxParallelEncodes = Get-ConfigInt 'MaxParallelEncodes' 1 1 2
$script:ParallelEncodeMode = if ($config.ContainsKey('ParallelEncodeMode')) {
    Resolve-MediaPipelineParallelEncodeMode -Mode ([string]$config['ParallelEncodeMode'])
} else {
    Get-MediaPipelineParallelEncodeModeDefault
}
if ($script:MaxParallelEncodes -gt 1 -and $script:ParallelEncodeMode -ne 'local_worker_slots') {
    Add-StartupWarning "MaxParallelEncodes is $script:MaxParallelEncodes but ParallelEncodeMode is '$script:ParallelEncodeMode'; local parallel encode scheduling remains disabled."
}
if ($script:ParallelEncodeMode -eq 'local_worker_slots' -and $script:MaxParallelEncodes -gt 1) {
    Add-StartupWarning "Parallel encode mode is enabled for $script:MaxParallelEncodes local worker slots. Use this only on dual-NVENC systems; it can increase disk, scratch-disk, CPU, memory, network, and source/output share pressure."
}

if ($config.ContainsKey('PreferredDefaultAudioLanguages')) {
    $v = $config['PreferredDefaultAudioLanguages']
    if     ($null -eq $v)       { $script:PreferredDefaultAudioLanguages = @() }
    elseif ($v -isnot [array])  { $script:PreferredDefaultAudioLanguages = @($v) }
    else                         { $script:PreferredDefaultAudioLanguages = @($v) }
} else {
    $script:PreferredDefaultAudioLanguages = @('english')
}
$script:PreferredDefaultAudioLanguages = @(
    $script:PreferredDefaultAudioLanguages |
        ForEach-Object { [string]$_ } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        ForEach-Object { $_.Trim() } |
        Select-Object -Unique
)
if ($script:PreferredDefaultAudioLanguages.Count -eq 0) {
    $script:PreferredDefaultAudioLanguages = @('english')
}

$legacyExtraVideoFlags = @($script:ExtraVideoFlags)
$script:EncodeTuningPreset = if ($config.ContainsKey('EncodeTuningPreset')) {
    Resolve-MediaPipelineEncodeTuningPreset -Preset ([string]$config['EncodeTuningPreset']) -LegacyExtraVideoFlags $legacyExtraVideoFlags
} else {
    Resolve-MediaPipelineEncodeTuningPreset -Preset '' -LegacyExtraVideoFlags $legacyExtraVideoFlags
}
$script:EncodeLadder = if ($config.ContainsKey('EncodeLadder')) {
    Resolve-MediaPipelineEncodeLadder -Ladder ([string]$config['EncodeLadder'])
} else {
    Get-MediaPipelineEncodeLadderDefault
}
$script:RoutingProfile = if ($config.ContainsKey('RoutingProfile')) {
    Resolve-MediaPipelineRoutingProfile -Profile ([string]$config['RoutingProfile'])
} else {
    Get-MediaPipelineRoutingProfileDefault
}
$script:SizeGuardMode = if ($config.ContainsKey('SizeGuardMode')) {
    Resolve-MediaPipelineSizeGuardMode -Mode ([string]$config['SizeGuardMode'])
} else {
    Get-MediaPipelineSizeGuardModeDefault
}
$script:AllowH264RemuxIfPlexCompatible = Get-ConfigBool 'AllowH264RemuxIfPlexCompatible' $true
$script:H264RemuxMaxBitrateMbps = Get-ConfigDouble 'H264RemuxMaxBitrateMbps' 35 1 500
$script:H264RemuxMaxHeight = Get-ConfigInt 'H264RemuxMaxHeight' 1080 1 4320
$script:MaxEncodeGrowthPercent = Get-ConfigDouble 'MaxEncodeGrowthPercent' 5 0 1000
$script:CompatibilityEncodeGrowthPercent = Get-ConfigDouble 'CompatibilityEncodeGrowthPercent' 15 0 1000
$script:CurrentSizePolicyResult = $null
$script:ExtraVideoFlags = @(
    Get-MediaPipelineEncodeTuningFlags `
        -Preset $script:EncodeTuningPreset `
        -Codec ([string]$script:VideoCodec) `
        -LegacyExtraVideoFlags $legacyExtraVideoFlags
)
if ($script:EncodeTuningPreset -eq 'custom_legacy_flags') {
    Add-StartupWarning 'EncodeTuningPreset resolved to custom_legacy_flags; freeform ExtraVideoFlags will be passed to ffmpeg unchanged.'
}

$legacyCompatibleAudioCodecs = if (Get-Variable -Name CompatibleAudioCodecs -Scope Script -ErrorAction SilentlyContinue) {
    @($script:CompatibleAudioCodecs)
} else {
    @()
}
$script:AudioPassthroughProfile = if ($config.ContainsKey('AudioPassthroughProfile')) {
    Resolve-MediaPipelineAudioPassthroughProfile -Profile ([string]$config['AudioPassthroughProfile']) -LegacyCompatibleAudioCodecs $legacyCompatibleAudioCodecs
} else {
    Resolve-MediaPipelineAudioPassthroughProfile -Profile '' -LegacyCompatibleAudioCodecs $legacyCompatibleAudioCodecs
}
if ($script:AudioPassthroughProfile -ne 'custom_codec_list') {
    $script:CompatibleAudioCodecs = @(Get-MediaPipelineAudioPassthroughProfileCodecs -Profile $script:AudioPassthroughProfile)
}
if ($script:AudioPassthroughProfile -eq 'custom_codec_list') {
    Add-StartupWarning 'AudioPassthroughProfile resolved to custom_codec_list; CompatibleAudioCodecs will be used as the passthrough policy.'
}

$script:AudioTranscodeCodec = Get-ConfigChoice 'AudioTranscodeCodec' 'eac3' @('eac3','ac3','aac')
$script:AudioTranscodeBitrate = if ($config.ContainsKey('AudioTranscodeBitrate')) {
    $rawAudioBitrate = ([string]$config['AudioTranscodeBitrate']).Trim().ToLowerInvariant()
    if ($rawAudioBitrate -match '^\d+k$') { $rawAudioBitrate } else {
        Add-StartupWarning "Config key 'AudioTranscodeBitrate' should look like 640k; using default 640k"
        '640k'
    }
} else {
    '640k'
}
$script:AudioDownmixMode = Get-ConfigChoice 'AudioDownmixMode' 'max_channels' @('preserve','max_channels','stereo')
$script:AudioMaxChannels = Get-ConfigInt 'AudioMaxChannels' 6 1 16
$script:AllowNoAudio = Get-ConfigBool 'AllowNoAudio' $false
# Suggestion #7 — opt-in channel-aware audio transcode bitrate. When
# $true, AudioTranscodeBitrate is ignored and per-stream bitrate is
# picked from a codec/channel-count table (eac3/ac3/aac). Default $false
# preserves existing behavior so operators with custom bitrates aren't
# surprised. Surfaced in the desktop config UI; see Get-AudioTranscode-
# BitrateForChannels in engine\audio\audio.ps1 for the table.
$script:AudioTranscodeAutoBitrateByChannels = Get-ConfigBool 'AudioTranscodeAutoBitrateByChannels' $false

# ==============================================================================
# PRODUCT AND PIPELINE VERSIONING
# ==============================================================================

# ProductVersion is the operator-facing release label shown in logs and titles.
# PipelineVersion is the sidecar compatibility version used by reprocess gates.
$script:ProductVersion = Get-MediaPipelineProductVersion
$script:PipelineVersion = Get-MediaPipelineSidecarVersion

# Minimum acceptable pipeline version for existing outputs. Outputs whose
# sidecar version is less than this trigger reprocessing even if the file
# already exists on the outsource. Defaults to the current version — i.e.
# files produced by older scripts are reprocessed once. Override to a
# specific older version (e.g. '0.9') to only reprocess files older
# than that.
$script:MinPipelineVersion = if ($config.ContainsKey('MinPipelineVersion') -and $config['MinPipelineVersion']) {
    [string]$config['MinPipelineVersion']
} else {
    $script:PipelineVersion
}

# Force reprocessing of EVERY file for one run, ignoring all sidecars.
# Useful for testing changes against the whole library. Set back to $false
# after the run or it'll loop forever.
$script:ReprocessAll = Get-ConfigBool 'ReprocessAll' $false
$script:DeferredPublish = Get-ConfigBool 'DeferredPublish' $false

# Estimated output-to-input size ratio used for the pre-encode disk check.
# At CQ 22 on the RTX 5080, HEVC output typically lands at 0.55–0.75x of
# the source depending on content. 0.7 is a safe headroom value.
$script:OutputSizeMultiplier = Get-ConfigDouble 'OutputSizeMultiplier' 0.7 0.1 2.0

# CQ value used when NVENC fails and the pipeline falls back to libx265.
# NVENC CQ 22 is roughly equivalent to libx265 CRF 19-20; 20 is a safe default.
$script:FallbackCpuQuality = Get-ConfigInt 'FallbackCpuQuality' 20 14 28

# libx265 -preset for CPU encodes (fallback or future primary).  Faster
# presets keep the box responsive but lose quality; slower presets compress
# better but can run for many hours.  Validation lives in
# Resolve-MediaPipelineCpuEncodePreset (engine\config\config_schema.ps1).
$script:CpuEncodePreset = if ($config.ContainsKey('CpuEncodePreset')) {
    Resolve-MediaPipelineCpuEncodePreset -Preset ([string]$config['CpuEncodePreset'])
} else {
    Get-MediaPipelineCpuEncodePresetDefault
}

# Windows ProcessPriorityClass to apply to ffmpeg when running a CPU encode.
# 'belownormal' keeps the desktop UI responsive while libx265 saturates cores;
# 'inherit' leaves the priority alone (legacy behavior).  Validation lives in
# Resolve-MediaPipelineCpuEncodeProcessPriority (engine\config\config_schema.ps1).
$script:CpuEncodeProcessPriority = if ($config.ContainsKey('CpuEncodeProcessPriority')) {
    Resolve-MediaPipelineCpuEncodeProcessPriority -Priority ([string]$config['CpuEncodeProcessPriority'])
} else {
    Get-MediaPipelineCpuEncodeProcessPriorityDefault
}

# E8 — Maximum libx265 threads. 0 = autodetect (libav default). >0 caps
# both libav -threads N and libx265 pools/frame-threads. Useful on small
# CPUs or when the desktop GUI must stay responsive during long encodes.
$script:CpuEncodeMaxThreads = Get-ConfigInt 'CpuEncodeMaxThreads' 0 0 256

$script:ConsoleLogLevel = Get-ConfigLogLevel 'ConsoleLogLevel' $(if ($DebugMode) { 'DEBUG' } else { 'INFO' })
$script:FileLogLevel    = Get-ConfigLogLevel 'FileLogLevel'    $(if ($DebugMode) { 'DEBUG' } else { 'INFO' })

# Per-show overrides. Hashtable keyed by GLOB PATTERN (case-insensitive)
# matching the TV show name. The match uses PowerShell -like semantics
# (supports * and ?). When a file matches, its override hashtable replaces
# the global defaults for that file only.
#
# Supported override keys:
#   DropAssAfterConversion  [bool]
#   DropTx3gAfterConversion [bool]
#   DropBdpgsAfterConversion [bool]
#   RemoveKaraoke           [bool]
#   KeepSignsAndSongs       [bool]
#   TreatAssSignsSongsAsForced  [bool]
#   TreatTx3gSignsSongsAsForced [bool]
#   TreatBdpgsSignsSongsAsForced [bool]
#   ExcludeSubtitleStyles   [array of glob patterns]
#   FlacAsCompatible        [bool]  — add 'flac' to CompatibleAudioCodecs
#                                     for this show only (useful for
#                                     music-heavy shows where EAC3 at 640k
#                                     would be a step down from stereo FLAC)
$script:ShowOverrides = @{}
if ($config.ContainsKey('ShowOverrides') -and $config['ShowOverrides'] -is [hashtable]) {
    $script:ShowOverrides = $config['ShowOverrides']
}

# Script-scope active-override slot. Resolve-ShowOverrides results are
# written here by Process-File before any downstream function runs. When
# $null, downstream functions use the $script:* globals as before.
$script:ActiveOverrides = $null

# Logical config validation
if ([double]$EncodeThresholdGB -le 0) {
    Add-StartupWarning "EncodeThresholdGB ($EncodeThresholdGB) must be > 0; using 8"
    $script:EncodeThresholdGB = 8
}
if ([double]$MinFreeSpaceGB -le 0) {
    Add-StartupWarning "MinFreeSpaceGB ($MinFreeSpaceGB) must be > 0; using 10"
    $script:MinFreeSpaceGB = 10
}

# Derived paths
$LocalIncoming        = Join-Path $LocalBase "Incoming"
$LocalEncoded         = Join-Path $LocalBase "Encoded"
$script:LocalStateLayout = New-MediaPipelineStateLayout -LocalBase $LocalBase
$LocalState           = $script:LocalStateLayout.Root
$LocalFailed          = $script:LocalStateLayout.Failures
$LocalFailureArtifacts = $script:LocalStateLayout.FailureArtifacts
$LocalFailureMarkers   = $script:LocalStateLayout.FailureMarkers
$LocalFailureReports   = $script:LocalStateLayout.FailureReports
# Completed-jobs manifest: an append-only JSONL log of every successful
# publish. Written locally (NOT on the outsource share) so the desktop
# app's Completed tab can list results without walking the SMB tree —
# which proved to be unacceptably slow/unreliable in the desktop UI.
# The canonical source of truth remains the .pipeline.json sidecar next
# to the output file; this manifest is a read-optimized mirror.
$LocalCompleted        = $script:LocalStateLayout.Completed
$CompletedJobsManifest = $script:LocalStateLayout.Paths.CompletedJobsManifest
$LocalRemuxTemp       = Join-Path $LocalBase "RemuxTemp"
# FIX#10: outputs whose server push failed are parked here instead of
# being deleted. The main loop retries them at the start of every round
# until they successfully land on the outsource.
$LocalPendingPush     = $script:LocalStateLayout.PendingPush
$RescanFlag           = $script:LocalStateLayout.Paths.RescanFlag
$LogFile              = Join-Path $LocalBase "pipeline_debug.log"
$PauseFlag            = $script:LocalStateLayout.Paths.PauseFlag
$StopFlag             = $script:LocalStateLayout.Paths.StopFlag
$ProgressFile         = $script:LocalStateLayout.Paths.ProgressFile
$PipelineEventLogFile = $script:LocalStateLayout.Paths.PipelineEventLogFile
$script:PipelineEventLogFile = $PipelineEventLogFile
$script:PipelineRunId = [guid]::NewGuid().ToString("N")
if ($WorkerChild -and -not [string]::IsNullOrWhiteSpace($WorkerRunId)) {
    $script:PipelineRunId = $WorkerRunId
}
$script:WorkerClaimId = if ($WorkerChild) { [string]$WorkerClaimId } else { '' }
$script:ProgressWriteFailures = 0
$script:ProgressPersistenceHealthy = $true
$LockFile             = Join-Path $LocalBase "pipeline.lock"
$script:processingDir = Join-Path $LocalIncoming "Processing"
$script:PendingPublishIndex = @{
    Count                 = 0
    BySourceIdentity      = @{}
    BySourceIdentityV2    = @{}
    ByServerOut           = @{}
    HasSourceIdentityV2   = $false
}
$script:FailureMarkerIndex = $null

if ($WorkerChild) {
    if ($WorkerSlotId -lt 1 -or $WorkerSlotId -gt 2) {
        Write-Host "FATAL: -WorkerChild requires -WorkerSlotId 1 or 2." -ForegroundColor Red
        exit 74
    }
    if ([string]::IsNullOrWhiteSpace($SingleFile)) {
        Write-Host "FATAL: -WorkerChild requires -SingleFile." -ForegroundColor Red
        exit 74
    }
    $script:WorkerSlotLayout = Initialize-MediaPipelineWorkerSlotLayout -SlotLayout (New-MediaPipelineWorkerSlotLayout -StateLayout $script:LocalStateLayout -SlotId $WorkerSlotId)
    $LocalIncoming        = $script:WorkerSlotLayout.Incoming
    $LocalEncoded         = $script:WorkerSlotLayout.Encoded
    $LocalRemuxTemp       = $script:WorkerSlotLayout.RemuxTemp
    $LocalFailed          = $script:WorkerSlotLayout.Failures
    $LogFile              = $script:WorkerSlotLayout.LogFile
    $ProgressFile         = $script:WorkerSlotLayout.ProgressFile
    $PipelineEventLogFile = $script:WorkerSlotLayout.EventLogFile
    $script:PipelineEventLogFile = $PipelineEventLogFile
    $LocalFailureArtifacts = $script:WorkerSlotLayout.FailureArtifacts
    $LocalFailureReports   = $script:WorkerSlotLayout.FailureReports
    $script:processingDir  = $script:WorkerSlotLayout.Processing
}

# ==============================================================================
# SINGLE INSTANCE LOCK — named OS Mutex (eliminates TOCTOU race from file+PID)
# ==============================================================================
$mutexSuffix = ''
if (-not [string]::IsNullOrWhiteSpace($env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX)) {
    $mutexSuffix = '_' + (($env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX) -replace '[^A-Za-z0-9_.-]', '_')
}
$instanceMutexName = "Global\MediaPipelineSingleInstance_v781$mutexSuffix"
$instanceMutex  = $null
$instanceLocked = $false
$workerSlotMutex = $null
$workerSlotLocked = $false
if (-not $ValidateOnly -and -not $WorkerChild) {
    $instanceMutex = [System.Threading.Mutex]::new($false, $instanceMutexName)
    try {
        $instanceLocked = $instanceMutex.WaitOne(0)
    } catch [System.Threading.AbandonedMutexException] {
        # Previous owner died without releasing — we can safely take ownership
        $instanceLocked = $true
    }
    if (-not $instanceLocked) {
        Write-Host "ERROR: Another instance of MediaPipeline is already running." -ForegroundColor Red
        if ($DrainPendingPushes) {
            Write-Host "       Publish parked outputs uses the same single-instance lock so pending manifests and copy operations cannot be drained twice."
        }
        Write-Host "       Stop the existing run or use the desktop Kill + Quit action, then try again."
        $instanceMutex.Dispose()
        exit 73
    }
}
if (-not $ValidateOnly -and $WorkerChild) {
    $workerSlotMutexName = Get-MediaPipelineLocalWorkerMutexName -Kind 'WorkerSlot' -LocalBase $LocalBase -SlotId $WorkerSlotId
    $workerSlotMutex = [System.Threading.Mutex]::new($false, $workerSlotMutexName)
    try {
        $workerSlotLocked = $workerSlotMutex.WaitOne(0)
    } catch [System.Threading.AbandonedMutexException] {
        $workerSlotLocked = $true
    }
    if (-not $workerSlotLocked) {
        Write-Host "ERROR: Another MediaPipeline worker child is already running for slot $WorkerSlotId." -ForegroundColor Red
        $workerSlotMutex.Dispose()
        exit 75
    }
}

$Script:ExitCleanup = {
    if ($logLock) { try { $logLock.ReleaseMutex(); $logLock.Dispose() } catch {} }
    if ($workerSlotMutex -and $workerSlotLocked) {
        try { $workerSlotMutex.ReleaseMutex(); $workerSlotMutex.Dispose() } catch {}
    }
    if ($instanceMutex -and $instanceLocked) {
        try { $instanceMutex.ReleaseMutex(); $instanceMutex.Dispose() } catch {}
    }
}
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action $Script:ExitCleanup | Out-Null

# ==============================================================================
# DEPENDENCY VALIDATION
# ==============================================================================
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot }
             elseif ($MyInvocation.MyCommand.Path) { Split-Path $MyInvocation.MyCommand.Path -Parent }
             else { (Get-Location).Path }
$script:SourceIdentityV2Algorithm = 'size-duration-codec-sample-v1'

$ffmpegPath   = Resolve-BundledExecutable -CommandName 'ffmpeg'   -RelativeCandidates @('Tools\ffmpeg\bin\ffmpeg.exe')
$ffprobePath  = Resolve-BundledExecutable -CommandName 'ffprobe'  -RelativeCandidates @('Tools\ffmpeg\bin\ffprobe.exe')
$mkvmergePath = Resolve-BundledExecutable -CommandName 'mkvmerge' -RelativeCandidates @('Tools\MKVToolNix\mkvmerge.exe')

if (-not $ffmpegPath -or -not $ffprobePath) {
    Write-Host "FATAL: bundled ffmpeg/ffprobe not found in Tools\\ffmpeg\\bin. Set AllowSystemTools=true only for development fallback." -ForegroundColor Red; exit 1
}
if (-not $mkvmergePath) {
    Write-Host "FATAL: bundled mkvmerge not found in Tools\\MKVToolNix. Set AllowSystemTools=true only for development fallback." -ForegroundColor Red; exit 1
}
if (-not (Get-Command robocopy -ErrorAction SilentlyContinue)) {
    Write-Host "FATAL: robocopy not found" -ForegroundColor Red; exit 1
}

# Python + pysubs2 check — subtitle conversion depends on these.
# Fail fast here rather than silently producing files with no subtitles.
$pythonPath = Resolve-BundledExecutable -CommandName 'python' -RelativeCandidates @(
    'Runtime\Python\python.exe',
    '..\DesktopApp\Runtime\Python\python.exe',
    'Tools\Python\python.exe'
)
if (-not $pythonPath) {
    Write-Host "FATAL: bundled python not found in Runtime\\Python, DesktopApp\\Runtime\\Python, or Tools\\Python. Set AllowSystemTools=true only for development fallback." -ForegroundColor Red; exit 1
}
$null = & $pythonPath -c "import pysubs2" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "FATAL: pysubs2 not installed. Run: pip install pysubs2" -ForegroundColor Red; exit 1
}

# Validate the Python helper script exists next to this script
$assToSrtScript = @(
    (Join-Path $scriptDir "ass_to_srt_chatgpt.py"),
    (Join-Path $scriptDir "ass_to_srt.py")
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not (Test-Path -LiteralPath $assToSrtScript)) {
    Write-Host "FATAL: ass_to_srt.py not found at $assToSrtScript" -ForegroundColor Red; exit 1
}

# ==============================================================================
# LOGGING
# ==============================================================================
# Keep the historical mutex name so mixed-version desktop/pipeline launches
# still serialize access to the same log file.
$logMutexName = "MediaPipelineLogMutex_v781$mutexSuffix"
$logLock = [System.Threading.Mutex]::new($false, $logMutexName)

# ==============================================================================
# STARTUP — directories first, then clean temp files
# ==============================================================================
Initialize-MediaPipelineStateLayout -Layout $script:LocalStateLayout -MigrateLegacy | Out-Null
foreach ($dir in @($LocalIncoming, $LocalEncoded, $LocalRemuxTemp, $script:processingDir)) {
    if (-not (Test-Path -LiteralPath $dir)) {
        [System.IO.Directory]::CreateDirectory($dir) | Out-Null
        Write-Host "Created directory: $dir"
    }
}

Invoke-LogRotation
if (-not $WorkerChild -and -not $ValidateOnly) {
    Repair-MediaPipelineLocalWorkerClaims -ClaimStorePath $script:LocalStateLayout.Paths.LocalWorkerClaims -CurrentRunId $script:PipelineRunId | Out-Null
    Write-MediaPipelineLocalWorkerActiveJobs -ActiveJobsPath $script:LocalStateLayout.Paths.LocalWorkerActiveJobs -CompatibilityProgressPath $ProgressFile -ActiveJobs @() -WriteCompatibilityProgress | Out-Null
}
Write-StartupWarnings

# ==============================================================================
# PIPELINE SIDECAR — versioning and reprocess detection
# ==============================================================================
if (-not (Test-PipelineVersionString $script:MinPipelineVersion)) {
    Write-Log "WARN: MinPipelineVersion '$($script:MinPipelineVersion)' is invalid - using $($script:PipelineVersion)" "WARN"
    $script:MinPipelineVersion = $script:PipelineVersion
} elseif (Compare-PipelineVersion $script:PipelineVersion $script:MinPipelineVersion) {
    Write-Log "WARN: MinPipelineVersion '$($script:MinPipelineVersion)' is newer than this script version '$($script:PipelineVersion)' - using current version" "WARN"
    $script:MinPipelineVersion = $script:PipelineVersion
}

# ==============================================================================
# FFMPEG PROGRESS MONITOR
# ==============================================================================
$Global:ffmpegProcess = $null
$script:FFmpegProgressWriteStepPercent = 5

$script:ProgressVersion = 2
$script:totalProcessed  = 0
$script:totalEncoded    = 0
$script:totalRemuxed    = 0
$script:totalFailed     = 0
$script:totalMovies     = 0
$script:totalTVEpisodes = 0
$script:SessionStartedAt = Get-Date
$script:currentFile     = "None"
$script:currentFileDisplay = $null
$script:currentFilePath = $null
$script:currentMediaType = $null
$script:currentQueuePhase = $null
$script:currentQueueIndex = 0
$script:currentQueueTotal = 0
$script:currentRoute = $null
$script:currentStage = 'initializing'
$script:currentStagePercent = $null
$script:currentItemStartedAt = $null
$script:currentStageStartedAt = Get-Date
$script:currentCopyState = $null
$script:currentPushState = $null
$script:currentSidecarState = $null
$script:pipelineStatus  = "Initializing"
$script:StopRequested   = $false
$script:LastPauseRequestId = $null
$script:LastPauseRequestCreatedAt = $null
$script:LastPauseRequestObservedAt = $null
$script:LastStopRequestId = $null
$script:LastStopRequestCreatedAt = $null
$script:LastStopRequestObservedAt = $null
$script:LastRescanRequestId = $null
$script:LastRescanRequestCreatedAt = $null
$script:LastRescanRequestObservedAt = $null
$script:SessionBaseline = $null
$script:RoundBaseline   = $null
$script:SessionSkipStats = @{}
$script:RoundSkipStats   = @{}
$script:SessionRetryCount = 0
$script:RoundRetryCount   = 0
$script:RoundMovieFilesFound = 0
$script:RoundTVFilesFound    = 0
$script:RoundFailureRecords  = [System.Collections.Generic.List[psobject]]::new()
$script:ProcessedIndexCache  = $null
$script:ProcessedIndexCacheAt = $null
$script:MovieScanCache       = @()
$script:MovieScanCacheAt     = $null
$script:TVScanCache          = @()
$script:TVScanCacheAt        = $null
$script:ForceProcessedIndexRefresh = $false

$progressReadPath = if (Test-Path $ProgressFile) {
    $ProgressFile
} elseif (Test-Path $script:LocalStateLayout.LegacyPaths.ProgressFile) {
    $script:LocalStateLayout.LegacyPaths.ProgressFile
} else {
    $null
}
if ($progressReadPath) {
    try {
        $saved = Get-Content $progressReadPath -Raw | ConvertFrom-Json
        $script:totalProcessed  = $saved.TotalProcessed
        $script:totalEncoded    = $saved.Encoded
        $script:totalRemuxed    = $saved.Remuxed
        $script:totalFailed     = $saved.Failed
        $script:totalMovies     = $saved.Movies
        $script:totalTVEpisodes = $saved.TVEpisodes
        Write-Log "Loaded previous progress: $($script:totalProcessed) files processed"
    } catch { Write-Log "Could not load progress file" "WARN" }
}

$script:SessionBaseline = Get-StatsSnapshot
$script:SessionSkipStats = New-SkipStats
Reset-RoundTracking

# ==============================================================================
# REMUX
# ==============================================================================

function Invoke-Tx3gSidecarExportForExistingOutput {
    param(
        [Parameter(Mandatory)] $SourceFile,
        [Parameter(Mandatory)] [string] $ScratchPath,
        [Parameter(Mandatory)] [string] $MediaOutputPath,
        [string] $Context = ''
    )

    if (-not $script:ConvertTx3gToSrt -or -not $script:CreateExternalTx3gSrtSidecars) { return $true }
    $subFilter = Filter-SubtitleStreams $ScratchPath $Context
    if ($subFilter.ProbeFailed) {
        Register-SourceFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Classification 'transient' -Reason ([string]$subFilter.Reason) -Stage 'subtitle-probe' -ErrorCode ([string]$subFilter.ErrorCode) -SuggestedAction 'Inspect ffprobe subtitle output and the source file; the pipeline will not silently publish an output with unknown subtitle state.' | Out-Null
        return $false
    }
    if (-not $subFilter.Tx3gConvert -or @($subFilter.Tx3gConvert).Count -eq 0) {
        return $true
    }

    $export = Export-Tx3gSrtSidecarsFromSource -FilterResult $subFilter -SourceFile $ScratchPath -MediaOutputPath $MediaOutputPath -Context $Context
    if ($export.Failures -and @($export.Failures).Count -gt 0) {
        Register-Tx3gSubtitleFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Failures @($export.Failures) -Stage 'subtitle-tx3g-extract'
        return $false
    }
    $written = @($export.Tracks | Where-Object { $_.status -eq 'written' }).Count
    $existing = @($export.Tracks | Where-Object { $_.status -eq 'existing' }).Count
    if (($written + $existing) -gt 0) {
        Write-Log "${Context}TX3G sidecars: $written written, $existing existing"
    }
    return $true
}

function Do-Remux {
    param($file, [bool]$isTV, $tvInfo)
    $safeName   = Get-SafeLocalName $file.Name
    $localIn    = $null
    $paths      = $null
    $tempAvFile = $null
    $subTracks  = $null
    # FIX#10: track successful server push. The finally block below only
    # deletes the local encoded output when $pushOk -eq $true, so a
    # network failure preserves the completed mkvmerge output in
    # PendingServerPush for the next run to retry.
    $pushOk     = $false
    $script:LastPublishResult = $null
    $script:CurrentSizePolicyResult = $null

    try {
        Set-ProgressStage -Stage 'copy_to_scratch' -Status $script:pipelineStatus -Route 'remux' -CopyState 'starting' -Percent $null -SaveNow
        $localIn = Ensure-ScratchCopy $file $safeName
        if (-not $localIn) { return $false }

        $paths = Get-OutputPaths $file $isTV $tvInfo $safeName
        if (Test-Path -LiteralPath $paths.ServerOut) {
            if (-not (Test-OutputNeedsReprocess -OutputPath $paths.ServerOut -SourceFile $file)) {
                if (-not (Invoke-Tx3gSidecarExportForExistingOutput -SourceFile $file -ScratchPath $localIn -MediaOutputPath $paths.ServerOut -Context "REMUX: ")) {
                    $localIn = $null
                    return $false
                }
                Write-Log "SKIP REMUX (exists on server): $(Split-Path $paths.ServerOut -Leaf)"
                Clear-SourceFailureState $file
                return $true
            }
            Write-Log "REMUX: reprocess mode - existing output will remain in place until the replacement is verified" "WARN"
        }
        if (-not (Test-DiskSpace $LocalBase -MinGB $MinFreeSpaceGB -Label "LOCAL")) { return $false }

        # R1 fix — remux peak scratch usage is ~2.5x source (input copy +
        # temp_av MKV + final MKV).  The headroom check above only checks
        # absolute MinFreeSpaceGB; without a source-scaled check, a 50 GB
        # UHD source on a 50 GB-free volume passes and then mkvmerge
        # exhausts the disk at 90% complete.
        if (-not (Test-EstimatedOutputSpace -SourcePath $localIn -Label "REMUX" -RemuxTwoStage)) {
            return $false
        }

        # R7 fix — Resolve-InitialMediaRoutePlan already populated
        # $script:CurrentRoutePlan.SourceCodec from the source-side ffprobe
        # in Get-SourceMediaRouteProfile.  Re-running ffprobe on the local
        # scratch copy here is redundant and adds 1-30s on slow disks.
        # Fall through to a probe only if the route plan didn't set the
        # codec (legacy / probe-failure path).
        $srcCodec = ''
        if ($script:CurrentRoutePlan -and $script:CurrentRoutePlan.PSObject.Properties['SourceCodec']) {
            $srcCodec = [string]$script:CurrentRoutePlan.SourceCodec
        }
        if ([string]::IsNullOrWhiteSpace($srcCodec) -or $srcCodec -eq 'unknown') {
            $srcCodec = Get-SourceVideoCodec $localIn
        }
        $codecRoutePlan = Resolve-RemuxCodecRoutePlan -SourceCodec $srcCodec -RemuxSafeVideoCodecs $RemuxSafeVideoCodecs -BasePlan $script:CurrentRoutePlan
        $script:CurrentRoutePlan = $codecRoutePlan
        $script:CurrentRouteReasonCode = [string]$codecRoutePlan.ReasonCode
        $script:CurrentRouteReason = [string]$codecRoutePlan.Reason
        if ($codecRoutePlan.Route -eq 'encode') {
            Write-Log "REMUX: $($codecRoutePlan.Reason)"
            # R7 fix — leave the scratch copy in place. Do-Encode calls
            # Ensure-ScratchCopy which is idempotent: it verifies the
            # fingerprint and integrity of the existing file and reuses
            # it (engine\storage\scratch_copy.ps1 — see the "Fingerprint matched and integrity
            # passed - reuse." branch in Ensure-ScratchCopy). Deleting it
            # here forced a second multi-GB copy from the network share
            # for every codec-fallback file.
            #
            # Suppress the local cleanup in our finally block so the
            # scratch survives the return into Do-Encode.
            $localIn = $null
            return Do-Encode $file $isTV $tvInfo
        }

        Set-ProgressStage -Stage 'remux_prepare' -Status $script:pipelineStatus -Route 'remux' -CopyState 'complete' -Percent 0 -SaveNow
        try {
            $audioArgs = Build-AudioArgs $localIn
        } catch {
            $reason = [string]$_.Exception.Message
            $errorCode = if ($reason -match 'SOURCE_MEDIA_AUDIO_MISSING') { 'SOURCE_MEDIA_AUDIO_MISSING' } elseif ($reason -match 'SOURCE_MEDIA_AUDIO_INVALID') { 'SOURCE_MEDIA_AUDIO_INVALID' } elseif ($reason -match 'SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED') { 'SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED' } else { 'AUDIO_ARGUMENT_BUILD_FAILED' }
            $classification = if ($errorCode -eq 'SOURCE_MEDIA_AUDIO_MISSING') { 'permanent' } else { 'transient' }
            $suggestedAction = if ($errorCode -eq 'SOURCE_MEDIA_AUDIO_MISSING') {
                'Replace the source with a media file that contains at least one audio stream, or add an explicit no-audio workflow before retrying.'
            } elseif ($errorCode -eq 'SOURCE_MEDIA_AUDIO_INVALID') {
                'Inspect ffprobe audio stream metadata and confirm the source file is complete; retry after replacing or repairing the source.'
            } elseif ($errorCode -eq 'SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED') {
                'Inspect ffprobe audio stream JSON and confirm the source is fully copied/unlocked; retry after repairing or replacing the source.'
            } else {
                'Inspect ffprobe audio output and the pipeline log; retry after correcting the source or tool failure.'
            }
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification $classification -Reason $reason -Stage 'audio-probe' -ErrorCode $errorCode -SuggestedAction $suggestedAction | Out-Null
            $localIn = $null
            return $false
        }
        # R6 fix — only the AV stage needs the source to be readable. We
        # do a quick subtitle-presence probe here (cheap), then run the
        # AV stage, and ONLY THEN run the expensive subtitle conversion
        # (TX3G->SRT, BDPGS OCR, ASS->SRT). Previously the OCR ran first
        # and was wasted whenever the AV stage exited corrupt.
        $defaultAudioLang = Get-DefaultAudioLang $localIn
        $subFilter        = Filter-SubtitleStreams $localIn "REMUX: "
        if ($subFilter.ProbeFailed) {
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason ([string]$subFilter.Reason) -Stage 'subtitle-probe' -ErrorCode ([string]$subFilter.ErrorCode) -SuggestedAction 'Inspect ffprobe subtitle output and the source file; the pipeline will not silently remux with unknown subtitle state.' | Out-Null
            $localIn = $null
            return $false
        }

        $tempAvFile = Join-Path $script:processingDir "temp_av_$([guid]::NewGuid().ToString('N')).mkv"
        # R4 fix — switch from "-map 0:v:0" (first video stream only) to
        # "-map 0:V" (all real video streams, excluding attached pictures
        # like cover art). Multi-angle Blu-ray and PiP commentary sources
        # used to lose alternate streams silently on remux while encode
        # would have kept them.
        # R3 fix — add "-map 0:t?" so embedded attachments (typeset fonts
        # for anime ASS rendering, cover art, etc.) survive the AV stage
        # into temp_av and through the final mkvmerge step. Encoded
        # outputs already preserved attachments; remuxed outputs did not.
        # R12 fix — switch "-map_metadata -1" to "-map_metadata 0" so
        # source provenance (encoder string, creation_time, custom user
        # tags) survives. mkvmerge's --title still overrides the title
        # field downstream.
        $videoArgs = [System.Collections.Generic.List[string]]::new()
        $videoArgs.AddRange([string[]]@(
            "-i", $localIn,
            "-map", "0:V", "-c:v", "copy"
        ))
        if ($srcCodec -in (Get-MediaVideoCodecHevcNames)) {
            # FFmpeg can reject HEVC stream-copy back into Matroska unless the
            # bitstream is normalized to Annex B. Apply to ALL HEVC video
            # output streams (the broader -map 0:V may produce more than
            # one) by using -bsf:v without an output-stream specifier.
            $videoArgs.AddRange([string[]]@("-bsf:v", "hevc_mp4toannexb"))
            Write-Log "REMUX: applying HEVC bitstream filter for Matroska stream-copy compatibility" "DEBUG"
        }

        # CPU-A6 — when audio transcode is active in the AV stage, cap
        # ffmpeg's libav thread budget too. -threads on a stream-copy-only
        # AV is harmless; on a transcode-active AV it prevents the audio
        # encoder from saturating cores.
        $threadCapArgs = @()
        if ([bool]$script:LastAudioTranscodeActive -and [int]$script:CpuEncodeMaxThreads -gt 0) {
            $threadCapArgs = @('-threads', [string]$script:CpuEncodeMaxThreads)
        }
        $ffAvArgs = @($videoArgs.ToArray()) + @(
            "-map", "0:t?",
            "-map_chapters", "0",
            "-map_metadata", "0"
        ) + $threadCapArgs + $audioArgs + @("-y", $tempAvFile)

        # CPU-A3 — when audio transcode is active the AV stage is no
        # longer pure stream-copy I/O — it's running an audio encoder
        # at full priority. Lower priority + acquire the machine-wide
        # CPU mutex (shared with libx265 fallback) so two concurrent
        # transcode-active remuxes can't both saturate the CPU.
        $remuxAvCpuLock = $null
        $remuxAvCpuEncode = [bool]$script:LastAudioTranscodeActive
        if ($remuxAvCpuEncode) {
            Write-Log "REMUX-AV: audio transcode active (priority $script:CpuEncodeProcessPriority, threads $(if ($script:CpuEncodeMaxThreads -gt 0) { $script:CpuEncodeMaxThreads } else { 'auto' }))" "DEBUG"
            $remuxAvCpuLock = Acquire-CpuEncodeMutex -TimeoutSeconds 0
            if (-not $remuxAvCpuLock.Acquired) {
                Write-Log "REMUX-AV: another CPU-bound job is already in progress on this machine; waiting for it ($($remuxAvCpuLock.Reason))" "WARN"
                Set-ProgressStage -Stage 'remux_av' -Status "Waiting for CPU slot (audio transcode)" -Route 'remux' -Percent 0 -SaveNow
                $remuxAvCpuLock = Acquire-CpuEncodeMutex -TimeoutSeconds $script:FFmpegRemuxTimeoutSeconds
            }
        }
        try {
            $remuxAvCallArgs = @{
                FFArgs          = $ffAvArgs
                Label           = 'REMUX-AV'
                InputFile       = $localIn
                TimeoutSeconds  = $script:FFmpegRemuxTimeoutSeconds
                ProgressStage   = 'remux_av'
                ProgressRoute   = 'remux'
                ReproStage      = 'remux-av'
            }
            if ($remuxAvCpuEncode) {
                $remuxAvCallArgs['CpuEncode']       = $true
                $remuxAvCallArgs['ProcessPriority'] = $script:CpuEncodeProcessPriority
            }
            $remuxAvSuccess = Invoke-FFmpegWithProgress @remuxAvCallArgs
        } finally {
            if ($remuxAvCpuLock -and $remuxAvCpuLock.Acquired) { & $remuxAvCpuLock.Release }
        }
        if (-not $remuxAvSuccess) {
            $reproPath = $script:LastFFmpegReproPath
            $ffmpegErrorSummary = Get-ErrorTextSummary -ErrorText $script:LastFFmpegStderr
            $errorCode = Get-FFmpegFailureCode -Stage 'remux-av' -ErrorText $script:LastFFmpegStderr -ExitCode ([int]$script:LastFFmpegExit)
            $reason = if ($ffmpegErrorSummary) { "FFmpeg remux AV stage failed: $ffmpegErrorSummary" } else { 'FFmpeg remux AV stage failed' }
            $suggestedAction = if ($errorCode -eq 'REMUX_HEVC_MKV_BITSTREAM_FAILED') {
                "This looks like an HEVC stream-copy to Matroska header failure. Retry with the updated pipeline so the primary video stream is mapped explicitly and hevc_mp4toannexb is applied."
            } elseif ($errorCode -eq 'REMUX_ATTACHED_PICTURE_MAPPED') {
                "This looks like attached cover art was mapped as video. Retry with the updated pipeline so only the primary video stream is selected."
            } else {
                "Inspect FFmpeg stderr log $($script:LastFFmpegErrorLog) and repro command $reproPath, then retry once the source/share issue is fixed."
            }
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'remux-av' -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction
            $localIn = $null
            return $false
        }

        # R6 fix — AV stage succeeded, source is known good. NOW run the
        # expensive subtitle conversion (BDPGS OCR can take many minutes
        # per language). Doing this earlier wasted that work whenever
        # the AV stage exited corrupt.
        $subTracks = Build-SubtitleTracksForMkvmerge $subFilter $defaultAudioLang $localIn "REMUX: "
        if ($subTracks.Failures -and @($subTracks.Failures).Count -gt 0) {
            Register-SubtitleExtractionFailure -SourceFile $file -ScratchPath $localIn -Failures @($subTracks.Failures) -Stage 'subtitle-extract'
            $localIn = $null
            return $false
        }

        [System.IO.Directory]::CreateDirectory($paths.LocalDir) | Out-Null
        [System.IO.Directory]::CreateDirectory($paths.ServerDir) | Out-Null

        # R10 fix — temp_av is now on disk and still ~1.0x source.
        # mkvmerge is about to write the third copy. Re-check before we
        # start, so we fail fast instead of half-way through a 50 GB mux.
        if (-not (Test-EstimatedOutputSpace -SourcePath $localIn -Label "REMUX-MUX" -RemuxFinalStage)) {
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason 'Insufficient scratch space for mkvmerge final mux' -Stage 'remux-mkvmerge' -ErrorCode 'REMUX_INSUFFICIENT_SPACE' -SuggestedAction 'Free space on the scratch volume or move LocalBase to a larger disk before retrying. The temp_av file is still consuming source-equivalent space and mkvmerge needs room for the final output.'
            return $false
        }

        $mkvArgs = [System.Collections.Generic.List[string]]::new()
        # FIX: removed --no-chapters so chapter data from tempAvFile is retained
        # R8 fix — Remux is content-preserving, so keep the source's title
        # tag when it has one (movie name, episode title, etc.). Only
        # stamp the generic "Encoded by MediaPipeline ..." title when the
        # source had no title.  Plex / Jellyfin fall back to this tag
        # when filename parsing is ambiguous.
        $sourceTitle = Get-SourceTitleTag -FilePath $localIn
        $effectiveTitle = if (-not [string]::IsNullOrWhiteSpace($sourceTitle)) {
            Write-Log "REMUX: preserving source title '$sourceTitle'" "DEBUG"
            $sourceTitle
        } else {
            "Encoded by MediaPipeline $($script:ProductVersion) (pipeline $($script:PipelineVersion))"
        }
        $mkvArgs.AddRange([string[]]@(
            "--output", $paths.LocalOut,
            "--title",  $effectiveTitle
        ))
        # R9 fix — emit explicit per-audio default-track flags. mkvmerge
        # needs absolute numeric TIDs (the global ID space across video,
        # audio, and subtitle tracks) — not audio-ordinal "aN". Probe
        # temp_av to translate Build-AudioArgs's audio ordinals to
        # mkvmerge TIDs. Without this, mkvmerge falls back to whatever
        # disposition ffmpeg stamped on the temp_av streams; in cross-
        # version cases that can leave more than one audio default.
        # mkvmerge `--default-track` flags must precede their input file.
        $audioTids = @(Get-MkvmergeAudioTids -FilePath $tempAvFile -Context "REMUX: ")
        if ($script:LastAudioTrackCount -gt 0 -and $audioTids.Count -ge $script:LastAudioTrackCount) {
            for ($aIdx = 0; $aIdx -lt $script:LastAudioTrackCount; $aIdx++) {
                $tid = [int]$audioTids[$aIdx]
                $isDefault = if ($aIdx -eq $script:LastAudioDefaultIndex) { 'yes' } else { 'no' }
                $mkvArgs.AddRange([string[]]@("--default-track", "$($tid):$isDefault"))
            }
        } elseif ($script:LastAudioTrackCount -gt 0) {
            Write-Log "REMUX: probed $($audioTids.Count) audio TIDs in temp_av but expected $($script:LastAudioTrackCount); skipping explicit default-track flags" "WARN"
        }
        $mkvArgs.Add($tempAvFile)
        if ($subTracks.SourceTracks.Count -gt 0) {
            foreach ($track in $subTracks.SourceTracks) {
                $mkvArgs.AddRange([string[]]@(
                    "--language",      "$($track.MkvTid):$($track.Lang)",
                    "--track-name",    "$($track.MkvTid):$($track.Title)",
                    "--default-track", "$($track.MkvTid):$(if ($track.IsDefault) { 'yes' } else { 'no' })"
                ))
                if ($track.IsForced) {
                    $mkvArgs.AddRange([string[]]@("--forced-track", "$($track.MkvTid):yes"))
                }
            }
            $mkvArgs.AddRange([string[]]@("--no-video","--no-audio","--subtitle-tracks",
                (($subTracks.SourceTracks | ForEach-Object { $_.MkvTid }) -join ","),$localIn))
        }
        foreach ($srt in $subTracks.ExternalTracks) {
            if (-not $srt.SrtPath) { continue }
            $mkvArgs.AddRange([string[]]@("--language","0:$($srt.Lang)","--track-name","0:$($srt.Title)",
                "--default-track","0:$(if ($srt.IsDefault) { 'yes' } else { 'no' })"))
            if ($srt.IsForced) { $mkvArgs.AddRange([string[]]@("--forced-track","0:yes")) }
            $mkvArgs.Add($srt.SrtPath)
        }

        Set-ProgressStage -Stage 'remux_mux' -Status $script:pipelineStatus -Route 'remux' -Percent 0 -SaveNow
        # R2 + R5 — use the configurable MkvmergeRemuxTimeoutSeconds (default
        # 7200 s, was a hard-coded 600 s) and the new --gui-mode-aware
        # progress wrapper so the GUI gets per-percent updates instead of
        # a frozen "remux mux" tile during multi-minute muxes.
        $mkv = Invoke-MkvmergeWithProgress -ArgumentList @($mkvArgs) -Label 'REMUX-MUX' -TimeoutSeconds $script:MkvmergeRemuxTimeoutSeconds -Stage 'remux-mkvmerge' -ProgressStage 'remux_mux' -ProgressRoute 'remux' -SaveReproOnFailure
        if ($mkv.ExitCode -ge 2) {
            $reproPath = $mkv.ReproPath
            $mkvLog = $null
            $mkvErrorSummary = Get-ErrorTextSummary -ErrorText $mkv.Error
            $errorCode = Get-MkvmergeFailureCode -ErrorText $mkv.Error -ExitCode ([int]$mkv.ExitCode) -TimedOut ([bool]$mkv.TimedOut) -Stopped ([bool]$mkv.Stopped)
            $reason = if ($mkvErrorSummary) { "mkvmerge failed with exit $($mkv.ExitCode): $mkvErrorSummary" } else { "mkvmerge failed with exit $($mkv.ExitCode)" }
            Write-Log "mkvmerge failed (exit $($mkv.ExitCode))" "ERROR"
            if ($mkv.Error) {
                $mkvLog = Join-Path $LocalFailed "mkvmerge_error_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
                try { $mkv.Error | Out-File -LiteralPath $mkvLog -Force } catch {}
                Write-Log "mkvmerge error log: $mkvLog" "ERROR"
                $mkv.Error -split '\r?\n' | Where-Object { $_ -match '\S' } |
                    Select-Object -Last 8 | ForEach-Object { Write-Log "  mkvmerge: $_" "ERROR" }
            }
            $suggestedAction = if ($mkvLog) {
                "Inspect mkvmerge stderr log $mkvLog and repro command $reproPath, then retry after fixing the subtitle/container issue."
            } else {
                "Inspect the saved mkvmerge repro command $reproPath, then retry after fixing the subtitle/container issue."
            }
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'remux-mkvmerge' -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction
            $localIn = $null
            return $false
        }
        if ($mkv.ExitCode -eq 1) { Write-Log "mkvmerge completed with warnings" "WARN" }

        if (-not (Test-Path -LiteralPath $paths.LocalOut) -or
            (Get-Item -LiteralPath $paths.LocalOut).Length -eq 0) {
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason 'REMUX output missing or empty after mkvmerge' -Stage 'remux-mkvmerge'
            $localIn = $null
            Write-Log "REMUX: output missing or empty after mkvmerge" "ERROR"; return $false
        }

        # Duration sanity check — catches silent truncations while tolerating
        # subtitle-tail container-duration differences on remuxed outputs.
        Set-ProgressStage -Stage 'remux_verify' -Status $script:pipelineStatus -Route 'remux' -Percent $null -SaveNow
        if (-not (Test-DurationMatch -SourcePath $localIn -OutputPath $paths.LocalOut -Label "REMUX" -AllowAVFallback)) {
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $paths.LocalOut -Classification 'transient' -Reason 'REMUX duration mismatch' -Stage 'remux-verify' -SuggestedAction 'Compare source and remuxed output A/V end times. Subtitle-tail container differences are tolerated now, so a remaining remux-verify failure usually indicates the output A/V is actually short.'
            Write-Log "REMUX: output duration mismatch - treating as failure" "ERROR"
            return $false
        }

        Write-PlexCompatibilityReport -FilePath $paths.LocalOut -Context "REMUX: "

        $publishResult = Complete-PipelineOutputPublish -SourceFile $file -ScratchPath $localIn -Paths $paths -Route 'remux' -ProgressRoute 'remux' -StagePrefix 'remux' -Context "REMUX: " -RouteReasonCode ([string]$script:CurrentRouteReasonCode) -RouteReason ([string]$script:CurrentRouteReason) -Tx3gTracks @($subTracks.Tx3gTracks) -BdpgsTracks @($subTracks.BdpgsTracks)
        $script:LastPublishResult = $publishResult
        if ($publishResult.DeleteLocalOutput) { $pushOk = $true }
        if ($publishResult.KeepScratchInput) { $localIn = $null }
        return [bool]$publishResult.Ok

    } catch {
        Write-Log "Do-Remux unexpected error: $_" "ERROR"
        Write-Log "Stack: $($_.ScriptStackTrace)" "DEBUG"
        if ($file) {
            $reason = "Do-Remux unexpected error: $($_.Exception.Message)"
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'remux-exception' -ErrorCode 'REMUX_UNEXPECTED_EXCEPTION' -SuggestedAction 'Inspect the pipeline log stack trace and failure artifact, then clear the marker after fixing the root cause.' | Out-Null
            $localIn = $null
        }
        return $false
    } finally {
        if ($tempAvFile)  { Remove-Item -LiteralPath $tempAvFile -Force -ErrorAction SilentlyContinue }
        if ($localIn)     {
            Remove-Item -LiteralPath $localIn -Force -ErrorAction SilentlyContinue
            Remove-ScratchFingerprint $localIn
            Remove-EmptyScratchContainer $localIn
        }
        # FIX#10: ONLY delete the local output when the server push
        # succeeded. On failure the output is already parked in
        # PendingServerPush by Invoke-ParkPendingPush.
        if ($pushOk -and $paths -and $paths.LocalOut -and
            (Test-Path -LiteralPath $paths.LocalOut -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $paths.LocalOut -Force -ErrorAction SilentlyContinue
        }
        if ($subTracks -and $subTracks.TempFiles) {
            $subTracks.TempFiles | ForEach-Object { Remove-Item -LiteralPath ([string]$_) -Force -ErrorAction SilentlyContinue }
        }
    }
}

# ==============================================================================
# ENCODE
# ==============================================================================
function Do-Encode {
    param($file, [bool]$isTV, $tvInfo)
    $safeName  = Get-SafeLocalName $file.Name
    $localIn   = $null
    $paths     = $null
    $tempOut   = $null
    $subResult = $null
    # FIX#10: same push-tracking flag pattern as Do-Remux.
    $pushOk    = $false
    $script:CurrentEncodeAttempts = @()
    $script:LastPublishResult = $null
    $script:CurrentSizePolicyResult = $null

    try {
        Set-ProgressStage -Stage 'copy_to_scratch' -Status $script:pipelineStatus -Route 'encode' -CopyState 'starting' -Percent $null -SaveNow
        $localIn = Ensure-ScratchCopy $file $safeName
        if (-not $localIn) { return $false }

        $paths = Get-OutputPaths $file $isTV $tvInfo $safeName
        if (Test-Path -LiteralPath $paths.ServerOut) {
            if (-not (Test-OutputNeedsReprocess -OutputPath $paths.ServerOut -SourceFile $file)) {
                if (-not (Invoke-Tx3gSidecarExportForExistingOutput -SourceFile $file -ScratchPath $localIn -MediaOutputPath $paths.ServerOut -Context "ENCODE: ")) {
                    $localIn = $null
                    return $false
                }
                Write-Log "SKIP ENCODE (exists on server): $(Split-Path $paths.ServerOut -Leaf)"
                Clear-SourceFailureState $file
                return $true
            }
            Write-Log "ENCODE: reprocess mode - existing output will remain in place until the replacement is verified" "WARN"
        }
        if (-not (Test-DiskSpace $LocalBase -MinGB $MinFreeSpaceGB -Label "LOCAL")) { return $false }

        # Pre-encode estimated output-size check. Fails fast if the scratch
        # drive can't hold the estimated output plus configured headroom,
        # instead of crashing mid-encode at 80%.
        if (-not (Test-EstimatedOutputSpace -SourcePath $localIn -Label "ENCODE")) {
            return $false
        }

        try {
            $hdrState = Get-HDRState $localIn
            if (-not [bool]$hdrState.Known) {
                throw "HDR_DETECTION_UNKNOWN: $($hdrState.Reason)"
            }
            $isHDR = [bool]$hdrState.IsHDR
        } catch {
            $reason = [string]$_.Exception.Message
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'hdr-detection' -ErrorCode 'HDR_DETECTION_UNKNOWN' -SuggestedAction 'Inspect ffprobe video stream metadata and confirm the source file is complete; retry after replacing or repairing the source.' | Out-Null
            $localIn = $null
            return $false
        }
        # Suggestion #1 — extract HDR10 mastering display + MaxCLL once per
        # file so any CPU-fallback x265 invocation can emit a complete
        # HDR10 SEI. Probe is best-effort: SDR sources / probes that fail
        # return Known=$false and we leave the metadata strings empty.
        $hdr10MasterDisplay = ''
        $hdr10MaxCll = ''
        if ($isHDR) {
            $hdr10Meta = Get-SourceHdr10MasteringMetadata -FilePath $localIn
            if ($hdr10Meta.Known) {
                if ($hdr10Meta.HasMasterDisplay) { $hdr10MasterDisplay = [string]$hdr10Meta.MasterDisplay }
                if ($hdr10Meta.HasMaxCll)        { $hdr10MaxCll        = [string]$hdr10Meta.MaxCll }
                Write-Log "ENCODE: HDR10 metadata found — master-display='$hdr10MasterDisplay' max-cll='$hdr10MaxCll'" "DEBUG"
            } else {
                Write-Log "ENCODE: HDR source but no HDR10 mastering metadata in side_data ($($hdr10Meta.Reason)); CPU-encoded HDR output will lack master-display/MaxCLL SEI" "WARN"
            }
        }
        $usingCpu    = $false
        $usingSafeRetry = $false
        $globalTitle = "Encoded by MediaPipeline $($script:ProductVersion) (pipeline $($script:PipelineVersion))"
        $recordEncodeAttempt = {
            param($Plan, [bool]$Succeeded)
            # D3 fix — record CPU-specific context per attempt so sidecar
            # consumers (analytics, diagnostics drawer) can correlate preset
            # / timeout / priority with success rate and elapsed time.
            # cpu_* fields are only meaningful for CPU attempts; GPU / safe
            # rows get empty/zero defaults so the schema stays uniform.
            $cpuPresetField = if ($Plan.PSObject.Properties['CpuPreset']) { [string]$Plan.CpuPreset } else { '' }
            $cpuTimeoutField = if ([bool]$Plan.UseCpuFallback) { [int]$script:FFmpegCpuEncodeTimeoutSeconds } else { 0 }
            $cpuPriorityField = if ([bool]$Plan.UseCpuFallback) { [string]$script:CpuEncodeProcessPriority } else { '' }
            $script:CurrentEncodeAttempts = @(@($script:CurrentEncodeAttempts) + ([ordered]@{
                attempt              = [string]$Plan.Attempt
                route                = [string]$Plan.Route
                label                = [string]$Plan.Label
                success              = [bool]$Succeeded
                used_cpu             = [bool]$Plan.UseCpuFallback
                safe_retry           = [bool]$Plan.UseSafeHardwareRetry
                repro_stage          = [string]$Plan.ReproStage
                encode_ladder        = [string]$Plan.EncodeLadder
                selected_encoder     = [string]$Plan.SelectedEncoder
                encoder_kind         = [string]$Plan.EncoderKind
                selected_gpu_device  = [string]$Plan.SelectedGpuDevice
                cpu_preset           = $cpuPresetField
                cpu_timeout_seconds  = $cpuTimeoutField
                cpu_process_priority = $cpuPriorityField
            }))
        }

        if ($isHDR) { Write-Log "ENCODE: HDR detected - Main10 / BT.2020" }
        else        { Write-Log "ENCODE: SDR - Main profile" }

        Set-ProgressStage -Stage 'encode_prepare' -Status $script:pipelineStatus -Route 'encode' -CopyState 'complete' -Percent 0 -SaveNow
        try {
            $audioArgs = Build-AudioArgs $localIn
        } catch {
            $reason = [string]$_.Exception.Message
            $errorCode = if ($reason -match 'SOURCE_MEDIA_AUDIO_MISSING') { 'SOURCE_MEDIA_AUDIO_MISSING' } elseif ($reason -match 'SOURCE_MEDIA_AUDIO_INVALID') { 'SOURCE_MEDIA_AUDIO_INVALID' } elseif ($reason -match 'SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED') { 'SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED' } else { 'AUDIO_ARGUMENT_BUILD_FAILED' }
            $classification = if ($errorCode -eq 'SOURCE_MEDIA_AUDIO_MISSING') { 'permanent' } else { 'transient' }
            $suggestedAction = if ($errorCode -eq 'SOURCE_MEDIA_AUDIO_MISSING') {
                'Replace the source with a media file that contains at least one audio stream, or add an explicit no-audio workflow before retrying.'
            } elseif ($errorCode -eq 'SOURCE_MEDIA_AUDIO_INVALID') {
                'Inspect ffprobe audio stream metadata and confirm the source file is complete; retry after replacing or repairing the source.'
            } elseif ($errorCode -eq 'SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED') {
                'Inspect ffprobe audio stream JSON and confirm the source is fully copied/unlocked; retry after repairing or replacing the source.'
            } else {
                'Inspect ffprobe audio output and the pipeline log; retry after correcting the source or tool failure.'
            }
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification $classification -Reason $reason -Stage 'audio-probe' -ErrorCode $errorCode -SuggestedAction $suggestedAction | Out-Null
            $localIn = $null
            return $false
        }
        $defaultAudioLang = Get-DefaultAudioLang $localIn
        $subFilter        = Filter-SubtitleStreams $localIn "ENCODE: "
        if ($subFilter.ProbeFailed) {
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason ([string]$subFilter.Reason) -Stage 'subtitle-probe' -ErrorCode ([string]$subFilter.ErrorCode) -SuggestedAction 'Inspect ffprobe subtitle output and the source file; the pipeline will not silently encode with unknown subtitle state.' | Out-Null
            $localIn = $null
            return $false
        }
        $subResult        = Build-SubtitleArgsForFFmpeg $subFilter $defaultAudioLang $localIn "ENCODE: "
        if ($subResult.Failures -and @($subResult.Failures).Count -gt 0) {
            Register-SubtitleExtractionFailure -SourceFile $file -ScratchPath $localIn -Failures @($subResult.Failures) -Stage 'subtitle-extract'
            $localIn = $null
            return $false
        }

        # Attempt 1 uses the configured GPU-first encoder. Retry policy and
        # CPU fallback command construction live in engine\decide\encode_policy.ps1.
        # Suggestion #2 — when the cached NVENC probe says GPU is
        # unavailable (set by Invalidate-NvencAvailableProbe after an
        # earlier runtime NVENC failure), skip the primary AND safe-retry
        # attempts entirely. Saves ~10–60 s per file on a no-GPU machine.
        $skipGpuDueToProbe = -not (Test-NvencProbeReportsAvailable)
        if ($skipGpuDueToProbe) {
            $probeReason = if ($script:NvencAvailableProbe -and $script:NvencAvailableProbe.Reason) { [string]$script:NvencAvailableProbe.Reason } else { 'NVENC probe cache reports unavailable' }
            Write-Log "ENCODE: NVENC unavailable per cached probe ($probeReason); skipping GPU-first ladder and going straight to CPU" "WARN"
            Write-PipelineEvent -EventType 'encoder_fallback_started' -Stage 'encode_cpu' -Route 'encode' -Status 'warn' -SourcePath $file.FullName -Data @{
                from_encoder = 'cached_unavailable'
                to_encoder   = (Get-MediaVideoCodecLibx265Name)
                reason       = $probeReason
                trigger      = 'nvenc_probe_unavailable'
                cpu_preset   = [string]$script:CpuEncodePreset
                is_hdr       = [bool]$isHDR
            } | Out-Null
        }

        $tempOut    = Join-Path $script:processingDir "encode_temp_$([guid]::NewGuid().ToString('N')).$OutputContainer"
        $encodePlan = New-EncodeAttemptPlan `
            -UseCpuFallback:$false `
            -IsTV:$isTV `
            -IsHDR:$isHDR `
            -InputPath $localIn `
            -ExtraInputs $subResult.ExtraInputs `
            -GlobalTitle $globalTitle `
            -AudioArgs $audioArgs `
            -SubtitleMapArgs $subResult.MapArgs `
            -OutputPath $tempOut `
            -VideoCodec $VideoCodec `
            -VideoPreset $VideoPreset `
            -VideoQuality $VideoQuality `
            -ExtraVideoFlags $ExtraVideoFlags `
            -FallbackCpuQuality $script:FallbackCpuQuality `
            -EncodeLadder $script:EncodeLadder `
            -CpuPreset $script:CpuEncodePreset `
                -CpuMaxThreads $script:CpuEncodeMaxThreads `
                -Hdr10MasterDisplay $hdr10MasterDisplay `
                -Hdr10MaxCll $hdr10MaxCll
        $ffArgs     = @($encodePlan.ArgumentList)

        $nullCount = @($ffArgs | Where-Object { $null -eq $_ }).Count
        if ($nullCount -gt 0) {
            Write-Log "ENCODE: $nullCount null element(s) in FFmpeg args - aborting" "ERROR"
            return $false
        }

        if ($skipGpuDueToProbe) {
            # Don't burn an ffmpeg launch for the primary GPU attempt;
            # synthesize the failure state so the existing fallback
            # branch fires and falls into the CPU path below.
            $success = $false
            $script:LastFFmpegStderr = "NVENC probe cache reports unavailable; primary GPU attempt skipped"
            $script:LastFFmpegExit = 1
        } else {
            $success = Invoke-FFmpegWithProgress $ffArgs $encodePlan.Label $localIn -TimeoutSeconds $script:FFmpegEncodeTimeoutSeconds -ProgressStage $encodePlan.ProgressStage -ProgressRoute $encodePlan.ProgressRoute -ReproStage $encodePlan.ReproStage
            & $recordEncodeAttempt $encodePlan ([bool]$success)
        }

        if (Test-ShouldRetryEncodeWithCpuFallback -Success:$success -StopRequested:$script:StopRequested -VideoCodec $VideoCodec -ErrorText $script:LastFFmpegStderr -ForceCpu:$skipGpuDueToProbe) {
            if (-not $skipGpuDueToProbe) {
                Write-Log "ENCODE: hardware encoder failure detected - retrying once with compatibility flags before CPU fallback" "WARN"
            }
            if (Test-Path -LiteralPath $tempOut) {
                Remove-Item -LiteralPath $tempOut -Force -ErrorAction SilentlyContinue
            }
            $tempOut    = Join-Path $script:processingDir "encode_temp_safe_$([guid]::NewGuid().ToString('N')).$OutputContainer"
            if (-not $skipGpuDueToProbe) {
                $encodePlan = New-EncodeAttemptPlan `
                    -UseCpuFallback:$false `
                    -UseSafeHardwareRetry:$true `
                    -IsTV:$isTV `
                    -IsHDR:$isHDR `
                    -InputPath $localIn `
                    -ExtraInputs $subResult.ExtraInputs `
                    -GlobalTitle $globalTitle `
                    -AudioArgs $audioArgs `
                    -SubtitleMapArgs $subResult.MapArgs `
                    -OutputPath $tempOut `
                    -VideoCodec $VideoCodec `
                    -VideoPreset $VideoPreset `
                    -VideoQuality $VideoQuality `
                    -ExtraVideoFlags $ExtraVideoFlags `
                    -FallbackCpuQuality $script:FallbackCpuQuality `
                    -EncodeLadder $script:EncodeLadder `
                    -CpuPreset $script:CpuEncodePreset `
                    -CpuMaxThreads $script:CpuEncodeMaxThreads `
                    -Hdr10MasterDisplay $hdr10MasterDisplay `
                    -Hdr10MaxCll $hdr10MaxCll
                $ffArgs     = @($encodePlan.ArgumentList)
                $success    = Invoke-FFmpegWithProgress $ffArgs $encodePlan.Label $localIn -TimeoutSeconds $script:FFmpegEncodeTimeoutSeconds -ProgressStage $encodePlan.ProgressStage -ProgressRoute $encodePlan.ProgressRoute -ReproStage $encodePlan.ReproStage
                & $recordEncodeAttempt $encodePlan ([bool]$success)
            } else {
                # GPU is already known unavailable; don't even build the
                # safe-retry plan. Force the inner gate to fall straight
                # into the CPU branch.
                $success = $false
                $script:LastFFmpegStderr = "NVENC probe cache reports unavailable; safe-retry skipped"
                $script:LastFFmpegExit = 1
            }
            if ($success) {
                $usingSafeRetry = $true
                $script:CurrentRouteReasonCode = 'hardware_encoder_safe_retry_succeeded'
                $script:CurrentRouteReason = 'hardware encoder failed with primary flags; compatibility retry succeeded'
            } elseif (Test-ShouldRetryEncodeWithCpuFallback -Success:$success -StopRequested:$script:StopRequested -VideoCodec $VideoCodec -ErrorText $script:LastFFmpegStderr -ForceCpu:$skipGpuDueToProbe) {
                # Suggestion #2 — second NVENC failure in this file means
                # the GPU is genuinely sick (driver hang, eGPU disconnect,
                # VRAM exhausted, etc.). Invalidate the probe cache so
                # the NEXT file goes straight to CPU instead of repeating
                # primary + safe-retry just to fail twice more. Skip when
                # we already came in via $skipGpuDueToProbe.
                if (-not $skipGpuDueToProbe) {
                    $invalidateReason = if ($script:LastFFmpegStderr) {
                        $tail = ($script:LastFFmpegStderr -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -Last 1)
                        "GPU primary + safe-retry both failed: $tail"
                    } else {
                        'GPU primary + safe-retry both failed'
                    }
                    Invalidate-NvencAvailableProbe -Reason $invalidateReason -SourcePath $file.FullName
                }
                Write-Log "ENCODE: compatibility retry also failed - falling back to $(Get-MediaVideoCodecLibx265Name) (CRF $($script:FallbackCpuQuality), preset $script:CpuEncodePreset, timeout $($script:FFmpegCpuEncodeTimeoutSeconds)s, priority $script:CpuEncodeProcessPriority)" "WARN"
                # Emit a structured event so the desktop diagnostics drawer
                # and the Live tab can light up a CPU-fallback indicator
                # instead of the operator only seeing a log line.
                Write-PipelineEvent -EventType 'encoder_fallback_started' -Stage 'encode_cpu' -Route 'encode' -Status 'warn' -SourcePath $file.FullName -Data @{
                    from_encoder         = [string]$VideoCodec
                    to_encoder           = (Get-MediaVideoCodecLibx265Name)
                    cpu_preset           = [string]$script:CpuEncodePreset
                    cpu_quality_crf      = [int]$script:FallbackCpuQuality
                    cpu_timeout_seconds  = [int]$script:FFmpegCpuEncodeTimeoutSeconds
                    cpu_process_priority = [string]$script:CpuEncodeProcessPriority
                    is_hdr               = [bool]$isHDR
                } | Out-Null
                if (Test-Path -LiteralPath $tempOut) {
                    Remove-Item -LiteralPath $tempOut -Force -ErrorAction SilentlyContinue
                }
                $tempOut    = Join-Path $script:processingDir "encode_temp_cpu_$([guid]::NewGuid().ToString('N')).$OutputContainer"
                # F-new-1 — re-validate scratch space with the CPU-aware
                # multiplier *before* the (potentially multi-hour) libx265
                # run. The original pre-flight at the top of Do-Encode used
                # the default 0.7x NVENC ratio, which can green-light an
                # encode that would actually fill the scratch volume at
                # 95% with libx265 output.
                if (-not (Test-EstimatedOutputSpace -SourcePath $localIn -Label "ENCODE-CPU" -IsCpuEncode)) {
                    Write-Log "ENCODE-CPU: insufficient scratch space for CPU-fallback encode — aborting before libx265 starts" "ERROR"
                    Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason 'Insufficient scratch space for CPU-fallback encode' -Stage 'encode' -ErrorCode 'ENCODE_CPU_INSUFFICIENT_SPACE' -SuggestedAction 'Free additional space on the scratch volume or lower CpuEncodePreset/FallbackCpuQuality before retrying. CPU encodes need 1:1 source-size headroom because libx265 output is typically larger than NVENC.' | Out-Null
                    $localIn = $null
                    return $false
                }
                $encodePlan = New-EncodeAttemptPlan `
                    -UseCpuFallback:$true `
                    -IsTV:$isTV `
                    -IsHDR:$isHDR `
                    -InputPath $localIn `
                    -ExtraInputs $subResult.ExtraInputs `
                    -GlobalTitle $globalTitle `
                    -AudioArgs $audioArgs `
                    -SubtitleMapArgs $subResult.MapArgs `
                    -OutputPath $tempOut `
                    -VideoCodec $VideoCodec `
                    -VideoPreset $VideoPreset `
                    -VideoQuality $VideoQuality `
                    -ExtraVideoFlags $ExtraVideoFlags `
                    -FallbackCpuQuality $script:FallbackCpuQuality `
                    -EncodeLadder $script:EncodeLadder `
                    -CpuPreset $script:CpuEncodePreset `
                -CpuMaxThreads $script:CpuEncodeMaxThreads `
                -Hdr10MasterDisplay $hdr10MasterDisplay `
                -Hdr10MaxCll $hdr10MaxCll
                $ffArgs     = @($encodePlan.ArgumentList)
                # Differentiate the GUI status string. app/status/service.py renders
                # `encode_cpu` with its own label, but the user-facing status
                # text (currentStatus) is also surfaced verbatim in the live
                # tile and the taskbar tooltip; keep it explicit so the
                # operator immediately knows this is a multi-hour CPU run.
                $cpuStatusText = if ($isTV) { "Encoding TV (CPU fallback)" } else { "Encoding Movie (CPU fallback)" }
                # F-new-4 — serialize CPU encodes machine-wide. If another
                # pipeline process on this box is already running libx265,
                # show the operator that we're queued behind it instead of
                # silently double-saturating the cores.
                $cpuMutexLock = Acquire-CpuEncodeMutex -TimeoutSeconds 0
                if (-not $cpuMutexLock.Acquired) {
                    Write-Log "ENCODE-CPU: another CPU encode is already in progress on this machine; waiting for it to finish ($($cpuMutexLock.Reason))" "WARN"
                    Set-ProgressStage -Stage 'encode_cpu' -Status "Waiting for CPU encode slot" -Route 'encode-cpu-fallback' -Percent 0 -SaveNow
                    $script:pipelineStatus = "Waiting for CPU encode slot"
                    # Wait up to the CPU encode timeout for the slot. Worst
                    # case the prior holder times out and releases.
                    $cpuMutexLock = Acquire-CpuEncodeMutex -TimeoutSeconds $script:FFmpegCpuEncodeTimeoutSeconds
                }
                Set-ProgressStage -Stage 'encode_cpu' -Status $cpuStatusText -Route 'encode-cpu-fallback' -Percent 0 -SaveNow
                $script:pipelineStatus = $cpuStatusText
                try {
                    # CPU encodes get their own (typically larger) timeout
                    # so a slow libx265 run is not killed at the 6-hour
                    # GPU ceiling.
                    $success    = Invoke-FFmpegWithProgress $ffArgs $encodePlan.Label $localIn -TimeoutSeconds $script:FFmpegCpuEncodeTimeoutSeconds -ProgressStage $encodePlan.ProgressStage -ProgressRoute $encodePlan.ProgressRoute -ReproStage $encodePlan.ReproStage -CpuEncode -ProcessPriority $script:CpuEncodeProcessPriority
                } finally {
                    if ($cpuMutexLock -and $cpuMutexLock.Acquired) { & $cpuMutexLock.Release }
                }
                & $recordEncodeAttempt $encodePlan ([bool]$success)
                if ($success) {
                    $usingCpu = $true
                    # E1 fix — keep the script-scope route state in sync with
                    # the actual encoder used. The size-policy guard (and any
                    # other consumer that reads CurrentRouteReasonCode during
                    # verify) needs to see the correct reason so CPU outputs
                    # receive the compatibility growth budget, not the strict 5%.
                    # Suggestion #2 — distinguish "GPU known unavailable per
                    # cached probe" from "GPU was actually attempted and
                    # failed for this file".  Both still use the
                    # encode-cpu-fallback route, but the reason code lets
                    # diagnostics show why GPU was skipped.
                    if ($skipGpuDueToProbe) {
                        $script:CurrentRouteReasonCode = 'gpu_unavailable_cpu_only'
                        $script:CurrentRouteReason     = 'NVENC unavailable per cached probe; CPU encode without trying GPU'
                    } else {
                        $script:CurrentRouteReasonCode = 'hardware_encoder_cpu_fallback'
                        $script:CurrentRouteReason     = 'hardware encoder failed; CPU fallback succeeded'
                    }
                    # E3 fix — mutate route_actions.video to 'encode_software'
                    # immediately on CPU success.  If a later verify/size-guard
                    # step rejects this output, the failure sidecar still has
                    # the correct encoder kind instead of the stale planned
                    # 'encode_hardware' label.
                    if ($script:CurrentRoutePlan -and $script:CurrentRoutePlan.PSObject.Properties['Actions']) {
                        $actions = $script:CurrentRoutePlan.Actions
                        if ($actions -is [System.Collections.IDictionary]) {
                            $actions['video'] = 'encode_software'
                        } else {
                            $videoProp = $actions.PSObject.Properties['video']
                            if ($videoProp) { $videoProp.Value = 'encode_software' }
                        }
                    }
                    # E5 paired event — operators correlating fallback start
                    # with completion get an explicit success record instead
                    # of inferring it from a later tool_completed.
                    Write-PipelineEvent -EventType 'encoder_fallback_completed' -Stage 'encode_cpu' -Route 'encode-cpu-fallback' -Status 'succeeded' -SourcePath $file.FullName -Data @{
                        from_encoder    = [string]$VideoCodec
                        to_encoder      = (Get-MediaVideoCodecLibx265Name)
                        cpu_preset      = [string]$encodePlan.CpuPreset
                        cpu_quality_crf = [int]$script:FallbackCpuQuality
                    } | Out-Null
                }
            }
        }

        if (-not $success) {
            $reproStage = if ($encodePlan -and $encodePlan.ReproStage) { [string]$encodePlan.ReproStage } elseif ($usingCpu) { 'encode-cpu' } else { 'encode' }
            $reproPath = $script:LastFFmpegReproPath
            $ffmpegErrorSummary = Get-ErrorTextSummary -ErrorText $script:LastFFmpegStderr
            $errorCode = Get-FFmpegFailureCode -Stage $reproStage -ErrorText $script:LastFFmpegStderr -ExitCode ([int]$script:LastFFmpegExit)
            # Encoder-aware reason / suggestion text. The previous text always
            # blamed NVENC even when the failed attempt was the CPU fallback,
            # which sent operators chasing the wrong root cause.
            $failedEncoderKind = if ($encodePlan -and $encodePlan.EncoderKind) { [string]$encodePlan.EncoderKind } elseif ($usingCpu) { 'cpu' } else { 'unknown' }
            $reasonPrefix = switch ($failedEncoderKind) {
                'cpu'   { 'FFmpeg CPU encode failed' }
                'nvenc' { 'FFmpeg NVENC encode failed' }
                default { 'FFmpeg encode failed' }
            }
            $reason = if ($ffmpegErrorSummary) { "${reasonPrefix}: $ffmpegErrorSummary" } else { $reasonPrefix }
            $suggestedAction = if ($failedEncoderKind -eq 'cpu') {
                "Inspect FFmpeg stderr log $($script:LastFFmpegErrorLog) and repro command $reproPath. The libx265 CPU fallback failed, so re-tuning NVENC will not help; check for source corruption, libx265 OOM (lower the preset or quality), or an x265 build issue."
            } else {
                "Inspect FFmpeg stderr log $($script:LastFFmpegErrorLog) and repro command $reproPath. If NVENC was unstable, compare against the CPU fallback behavior."
            }
            # D2 fix — CPU failures are recorded as 'transient' just like
            # NVENC failures. Register-SourceFailure already escalates to
            # 'operator_required' after $TransientFailureRetryLimit repeated
            # same-(stage,error_code) failures (see engine\failures\failure_state.ps1
            # ~line 670). That gives a CPU job N retry chances for
            # genuinely transient errors (antivirus locks, transient OOM,
            # disk full near end), then escalates exactly once instead of
            # the previous "first failure is permanent" behavior.
            # Emit the matching encoder_fallback_completed event so the
            # diagnostics drawer can pair start with end (E5).
            if ($failedEncoderKind -eq 'cpu') {
                Write-PipelineEvent -EventType 'encoder_fallback_completed' -Stage 'encode_cpu' -Route 'encode-cpu-fallback' -Status 'failed' -SourcePath $file.FullName -Data @{
                    from_encoder    = [string]$VideoCodec
                    to_encoder      = (Get-MediaVideoCodecLibx265Name)
                    cpu_preset      = if ($encodePlan -and $encodePlan.PSObject.Properties['CpuPreset']) { [string]$encodePlan.CpuPreset } else { '' }
                    cpu_quality_crf = [int]$script:FallbackCpuQuality
                    error_code      = [string]$errorCode
                } | Out-Null
            }
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'encode' -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction
            $localIn = $null
            Write-Log "ENCODE failed - recorded as transient and scheduled for retry: $safeName" "ERROR"
            return $false
        }

        if (-not (Test-Path -LiteralPath $tempOut) -or (Get-Item -LiteralPath $tempOut).Length -eq 0) {
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason 'ENCODE output missing or empty after ffmpeg' -Stage 'encode'
            $localIn = $null
            Write-Log "ENCODE: output missing or empty after ffmpeg" "ERROR"; return $false
        }

        # Duration sanity check — catches silent truncations.
        # AllowAVFallback tolerates the common case where an ASS subtitle cue
        # extends past the actual A/V end, inflating the source container duration.
        # D5 fix — preserve the encode-cpu-fallback route badge through the
        # verify stage so the GUI doesn't briefly drop the CPU label between
        # encode_cpu (100%) and the publish step.
        $verifyRoute = if ($usingCpu) { 'encode-cpu-fallback' } elseif ($usingSafeRetry) { 'encode-safe-retry' } else { 'encode' }
        Set-ProgressStage -Stage 'encode_verify' -Status $script:pipelineStatus -Route $verifyRoute -Percent $null -SaveNow
        if (-not (Test-DurationMatch -SourcePath $localIn -OutputPath $tempOut -Label "ENCODE" -AllowAVFallback)) {
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason 'ENCODE duration mismatch' -Stage 'encode-verify' -SuggestedAction 'Compare source and encoded output A/V end times. Container-duration differences caused by subtitle tails are tolerated, so a remaining encode-verify failure usually means the output A/V is genuinely shorter than the source.'
            $localIn = $null
            Write-Log "ENCODE: duration mismatch - recorded as transient and scheduled for retry: $safeName" "ERROR"
            return $false
        }

        $sizePolicy = Test-MediaEncodeOutputSizePolicy `
            -SourcePath $localIn `
            -OutputPath $tempOut `
            -RoutingProfile $script:RoutingProfile `
            -SizeGuardMode $script:SizeGuardMode `
            -MaxGrowthPercent $script:MaxEncodeGrowthPercent `
            -CompatibilityGrowthPercent $script:CompatibilityEncodeGrowthPercent `
            -RouteReasonCode ([string]$script:CurrentRouteReasonCode)
        $script:CurrentSizePolicyResult = $sizePolicy.Metadata
        if ($sizePolicy.Exceeded) {
            $sizePolicySeverity = ([string]$sizePolicy.Severity).ToUpperInvariant()
            Write-Log "ENCODE SIZE: $($sizePolicy.Message)" $sizePolicySeverity
        } else {
            Write-Log "ENCODE SIZE: $($sizePolicy.Message)" "DEBUG"
        }
        if (-not $sizePolicy.Ok) {
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'operator_required' -Reason ([string]$sizePolicy.Message) -Stage 'encode-size-policy' -ErrorCode 'ENCODE_SIZE_GUARD_EXCEEDED' -SuggestedAction 'Review the source and routing policy. Use advisory/off size guard, force remux for a compatible source, or adjust encode quality/ladder before retrying.'
            $localIn = $null
            Write-Log "ENCODE: output rejected by strict size policy: $safeName" "ERROR"
            return $false
        }

        [System.IO.Directory]::CreateDirectory($paths.LocalDir) | Out-Null
        [System.IO.Directory]::CreateDirectory($paths.ServerDir) | Out-Null

        [System.IO.File]::Move($tempOut, $paths.LocalOut, $true)
        $tempOut = $null

        Write-PlexCompatibilityReport -FilePath $paths.LocalOut -Context "ENCODE: "

        # CurrentRouteReasonCode/Reason and route_actions.video are already
        # synchronized at the point $usingCpu / $usingSafeRetry was set. The
        # locals below are derived for the publish call only; do not re-mutate
        # script-scope state here (see E1 / E3 fixes).
        $route = if ($usingCpu) { "encode-cpu-fallback" } elseif ($usingSafeRetry) { "encode-safe-retry" } else { "encode" }
        $routeReasonCode = [string]$script:CurrentRouteReasonCode
        $routeReason     = [string]$script:CurrentRouteReason
        $publishResult = Complete-PipelineOutputPublish -SourceFile $file -ScratchPath $localIn -Paths $paths -Route $route -ProgressRoute 'encode' -StagePrefix 'encode' -Context "ENCODE: " -RouteReasonCode $routeReasonCode -RouteReason $routeReason -Tx3gTracks @($subResult.Tx3gTracks) -BdpgsTracks @($subResult.BdpgsTracks)
        $script:LastPublishResult = $publishResult
        if ($publishResult.DeleteLocalOutput) { $pushOk = $true }
        if ($publishResult.KeepScratchInput) { $localIn = $null }
        return [bool]$publishResult.Ok

    } catch {
        Write-Log "Do-Encode unexpected error: $_" "ERROR"
        Write-Log "Stack: $($_.ScriptStackTrace)" "DEBUG"
        if ($file) {
            $reason = "Do-Encode unexpected error: $($_.Exception.Message)"
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'encode-exception' -ErrorCode 'ENCODE_UNEXPECTED_EXCEPTION' -SuggestedAction 'Inspect the pipeline log stack trace and failure artifact, then clear the marker after fixing the root cause.' | Out-Null
            $localIn = $null
        }
        return $false
    } finally {
        if ($subResult -and $subResult.TempFiles) {
            $subResult.TempFiles | ForEach-Object { Remove-Item -LiteralPath ([string]$_) -Force -ErrorAction SilentlyContinue }
        }
        if ($tempOut -and (Test-Path -LiteralPath $tempOut -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $tempOut -Force -ErrorAction SilentlyContinue
        }
        if ($localIn -and (Test-Path -LiteralPath $localIn -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $localIn -Force -ErrorAction SilentlyContinue
            Remove-ScratchFingerprint $localIn
            Remove-EmptyScratchContainer $localIn
        }
        # FIX#10: ONLY delete local encoded output when server push
        # succeeded. On failure Invoke-ParkPendingPush has already moved
        # the file to PendingServerPush; deleting here would destroy
        # hours of encode work.
        if ($pushOk -and $paths -and $paths.LocalOut -and
            (Test-Path -LiteralPath $paths.LocalOut -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $paths.LocalOut -Force -ErrorAction SilentlyContinue
        }
    }
}

# ==============================================================================
# PROCESS ONE FILE
# ==============================================================================
# ==============================================================================
# PROCESS ONE FILE
# ===============================================================================
# Compatibility wrapper: the job-level implementation lives in
# engine\process\pipeline_processing.ps1 so the engine can call the historical name.
function Process-File {
    param(
        $file,
        [bool]$isTV,
        $idx,
        [int]$QueueIndex = 0,
        [int]$QueueTotal = 0,
        $PriorityInfo = $null
    )

    Invoke-MediaPipelineProcessFile -file $file -isTV:$isTV -idx $idx -QueueIndex $QueueIndex -QueueTotal $QueueTotal -PriorityInfo $PriorityInfo
}

# Queue snapshot helpers live in engine\queue\pipeline_engine.ps1.

# ==============================================================================
# MAIN LOOP
# ==============================================================================
if (-not $ValidateOnly) {
    Clear-OldTempFiles
    # FIX#6: sweep any stale .mp-partial files from crashed prior runs so we
    # don't confuse them with in-flight copies.
    if ($DrainPendingPushes) {
        Write-Log "DRAIN PENDING PUSHES: skipping startup stale-partial cleanup scans; copy retries clean their own staging."
    } else {
        Clear-StalePartialFiles -Roots @($LocalEncoded, $Outsource)
    }
}

if (-not $ValidateOnly) {
    foreach ($flag in @($PauseFlag, $StopFlag)) {
        if (Test-Path -LiteralPath $flag) { Remove-Item -LiteralPath $flag -Force -ErrorAction SilentlyContinue }
    }
}

Write-Log "===== PIPELINE START $($script:ProductVersion) (pipeline $($script:PipelineVersion)) ====="
$runMode = if ($ValidateOnly) { 'validate-only' } elseif ($WorkerChild) { 'local-worker-child' } elseif ($DrainPendingPushes) { 'drain-pending-pushes' } elseif ($Once) { 'single-pass' } else { 'continuous' }
Write-PipelineEvent -EventType 'pipeline_started' -Stage 'startup' -Status 'started' -Data @{
    run_mode    = $runMode
    config_path = $configPath
    local_base  = $LocalBase
} | Out-Null
Write-Log "Run mode      : $runMode"
Write-Log "Config file   : $configPath"
Write-Log "PowerShell    : $($PSVersionTable.PSVersion)"
Write-Log "SleepSeconds  : $SleepSeconds"
$workerSlotLog = if ($WorkerChild) { " worker_slot=$WorkerSlotId" } else { "" }
Write-Log "Parallel encodes: max=$script:MaxParallelEncodes mode=$script:ParallelEncodeMode$workerSlotLog"
Write-Log "Scan refresh  : source $($script:SourceScanIntervalSeconds)s | index $($script:ProcessedIndexRefreshSeconds)s"
Write-Log "Movie thresh  : $EncodeThresholdGB GB | TV thresh: $TVEncodeThresholdGB GB"
Write-Log "Codec         : $VideoCodec preset $VideoPreset CQ $VideoQuality"
Write-Log "Encode tuning : $script:EncodeTuningPreset flags=$($script:ExtraVideoFlags -join ' ')"
Write-Log "Encode ladder : $script:EncodeLadder"
Write-Log "Routing profile: $script:RoutingProfile"
Write-Log "H.264 copy    : $script:AllowH264RemuxIfPlexCompatible (<= $($script:H264RemuxMaxBitrateMbps) Mbps, <= $($script:H264RemuxMaxHeight)p)"
Write-Log "Size guard    : $script:SizeGuardMode (default +$($script:MaxEncodeGrowthPercent)%; compatibility +$($script:CompatibilityEncodeGrowthPercent)%)"
Write-Log "Remux-safe    : $($RemuxSafeVideoCodecs -join ', ')"
Write-Log "Audio profile : $script:AudioPassthroughProfile"
Write-Log "Audio compat  : $($script:CompatibleAudioCodecs -join ', ')"
Write-Log "Audio policy  : transcode=$script:AudioTranscodeCodec $script:AudioTranscodeBitrate downmix=$script:AudioDownmixMode max_ch=$script:AudioMaxChannels allow_no_audio=$script:AllowNoAudio"
Write-Log "Drop ASS      : $DropAssAfterConversion"
$tx3gLanguageText = ($script:Tx3gExtractLanguages -join ', ')
$bdpgsLanguageText = ($script:BdpgsExtractLanguages -join ', ')
$bdpgsOcrToolText = if ($script:BdpgsOcrToolPath) { $script:BdpgsOcrToolPath } else { '(not configured)' }
Write-Log ("Convert TX3G  : {0} (languages: {1}; drop original: {2}; external sidecars: {3}; preserve existing SRT: {4})" -f $script:ConvertTx3gToSrt, $tx3gLanguageText, $script:DropTx3gAfterConversion, $script:CreateExternalTx3gSrtSidecars, $script:Tx3gPreserveExistingSrt)
Write-Log ("Convert BDPGS : {0} (languages: {1}; drop original: {2}; OCR tool: {3})" -f $script:ConvertBdpgsToSrt, $bdpgsLanguageText, $script:DropBdpgsAfterConversion, $bdpgsOcrToolText)
Write-Log "Signs/Songs   : keep ASS=$($script:KeepSignsAndSongs) | ASS forced=$($script:TreatAssSignsSongsAsForced) | TX3G forced=$($script:TreatTx3gSignsSongsAsForced) | BDPGS forced=$($script:TreatBdpgsSignsSongsAsForced)"
Write-Log "Merge adjacent: $($script:MergeAdjacent) (threshold: $($script:MergeThresholdMs)ms)"
Write-Log "Remove karaoke: $($script:RemoveKaraoke)"
if ($script:ExcludeSubtitleStyles.Count -gt 0) {
    Write-Log "Exclude styles: $($script:ExcludeSubtitleStyles -join ', ')"
} else {
    Write-Log "Exclude styles: (using Python defaults)"
}
Write-Log "Log retention : $($script:LogRetentionDays) days"
Write-Log "Log levels    : console=$($script:ConsoleLogLevel) | file=$($script:FileLogLevel)"
Write-Log "Product ver   : $($script:ProductVersion)"
Write-Log "Pipeline ver  : $($script:PipelineVersion) (min for reprocess: $($script:MinPipelineVersion))"
Write-Log "ReprocessAll  : $($script:ReprocessAll)"
Write-Log "Deferred publish : $($script:DeferredPublish)"
Write-Log "Aggressive TV parse : $($script:AggressiveEpisodeParsing)"
Write-Log ("CPU fallback  : {0} CRF {1} preset {2} threads={3} (process priority: {4})" -f (Get-MediaVideoCodecLibx265Name), $script:FallbackCpuQuality, $script:CpuEncodePreset, $(if ($script:CpuEncodeMaxThreads -gt 0) { [string]$script:CpuEncodeMaxThreads } else { 'auto' }), $script:CpuEncodeProcessPriority)
Write-Log "FFmpeg timeouts: encode $($script:FFmpegEncodeTimeoutSeconds)s | encode-cpu $($script:FFmpegCpuEncodeTimeoutSeconds)s | remux $($script:FFmpegRemuxTimeoutSeconds)s | mkvmerge $($script:MkvmergeRemuxTimeoutSeconds)s | subtitle extract $($script:SubtitleExtractTimeoutSeconds)s | subtitle probe $($script:SubtitleProbeTimeoutSeconds)s | BDPGS OCR $($script:BdpgsOcrTimeoutSeconds)s"

# F-new-2 — probe NVENC availability once at startup and cache. The
# probe binds to the configured VideoCodec when it's an nvenc encoder so
# we test the same codec the pipeline will try first per file.
$nvencTestEncoder = if ($VideoCodec -match 'nvenc') { $VideoCodec } else { 'hevc_nvenc' }
$nvencProbe = Test-NvencAvailable -TestEncoder $nvencTestEncoder
$script:NvencAvailableProbe = $nvencProbe
if ($nvencProbe.Available) {
    Write-Log "NVENC probe   : OK ($nvencTestEncoder usable on this host)"
} else {
    $reasonText = if ($nvencProbe.Reason) { $nvencProbe.Reason } else { 'unknown' }
    Write-Log "NVENC probe   : NOT AVAILABLE ($reasonText) — primary encode will fall back to libx265 (CPU) for every file" "WARN"
    Write-Log "                CPU encode preset=$script:CpuEncodePreset CRF=$script:FallbackCpuQuality timeout=$($script:FFmpegCpuEncodeTimeoutSeconds)s — expect multi-hour runs per file" "WARN"
    Write-PipelineEvent -EventType 'gpu_unavailable' -Stage 'startup' -Status 'warn' -Data @{
        encoder         = $nvencTestEncoder
        reason          = [string]$nvencProbe.Reason
        encoder_listed  = [bool]$nvencProbe.EncoderListMatch
        runtime_probed  = [bool]$nvencProbe.Probed
    } | Out-Null
}
Write-Log "Copy/scan timeouts: robocopy $($script:RobocopyTimeoutSeconds)s | source scan $($script:SourceScanTimeoutSeconds)s | index scan $($script:IndexScanTimeoutSeconds)s"
Write-Log "Output size mult: $($script:OutputSizeMultiplier)x (for pre-encode disk check)"
Write-Log "Priority tags : $(if ($script:PriorityMarkers.Count -gt 0) { $script:PriorityMarkers -join ', ' } else { '(none)' })"
Write-StartupEnvironmentSummary

# ==============================================================================
# STARTUP PATH VALIDATION
# ------------------------------------------------------------------------------
# Validate critical paths before entering the scan loop. A typo or a
# permanently missing path otherwise causes silent skip-all behaviour: the
# pipeline runs normally, logs "0 files found", and the user never knows
# something is wrong.
#
#  LocalBase     — hard fail: without it we can't write logs, progress, or
#                  scratch files; there is nothing useful we can do.
#  Source shares — soft warn: they may be temporarily offline (NAS reboot,
#                  VPN drop). The pipeline will loop and retry each scan.
#  Outsource     — soft warn: same rationale; temporary outages are normal.
#  Drain mode    — skips source/output probes because it only retries parked
#                  manifest payloads and each copy validates its destination.
# ==============================================================================
$localBaseReachable = Test-PathAccessibleBounded -Path $LocalBase -TimeoutSeconds 10
if ($localBaseReachable -ne $true) {
    $reachability = if ($null -eq $localBaseReachable) { 'timed out while checking' } else { 'does not exist or is not accessible' }
    Write-Log "FATAL: LocalBase does not exist or is not accessible: $LocalBase" "ERROR"
    Write-Log "       Path check result: $reachability" "ERROR"
    Write-Log "       Check the LocalBase setting in your config file." "ERROR"
    Write-Log "PIPELINE ABORTED"
    exit 2
}
if ($DrainPendingPushes) {
    Write-Log "DRAIN PENDING PUSHES: publish-only mode skips SourceMovies/SourceTV/Outsource startup reachability probes; pending manifest copy attempts validate their destinations."
} else {
    foreach ($pair in @(
        @{ Label = 'SourceMovies'; Path = $SourceMovies },
        @{ Label = 'SourceTV';     Path = $SourceTV },
        @{ Label = 'Outsource';    Path = $Outsource }
    )) {
        $reachable = Test-PathAccessibleBounded -Path ([string]$pair.Path) -TimeoutSeconds 10
        if ($reachable -ne $true) {
            $reachability = if ($null -eq $reachable) { 'check timed out' } else { 'path is not accessible' }
            Write-Log "STARTUP WARNING: $($pair.Label) is not accessible: $($pair.Path)" "WARN"
            Write-Log "                 Path check result: $reachability." "WARN"
            Write-Log "                 Scans for this location will return 0 files until it is reachable." "WARN"
        }
    }
}

if (-not (Test-ProgressPersistence)) {
    $script:ProgressWriteFailures = 3
    Write-Log "Progress persistence is unavailable; processing will not start until LocalBase is writable." "ERROR"
}
# Verify ass_to_srt script is importable before processing any files.
# Exit code 2 means "loaded OK, wrong arg count" — the normal arg-guard path.
# Any other exit code means the script crashed at import time; every ASS->SRT
# conversion attempt will silently fall back to keeping the raw ASS track.
if ($DrainPendingPushes) {
    Write-Log "DRAIN PENDING PUSHES: skipping subtitle helper self-check; parked sidecars are already materialized."
} else {
    $_assCheck = Invoke-PythonToolCommand -ArgumentList @($assToSrtScript) -TimeoutSeconds 15 -Stage 'subtitle-helper-selfcheck'
    if ($_assCheck.ExitCode -ne 2) {
        Write-Log "STARTUP: ass_to_srt import check FAILED (exit $($_assCheck.ExitCode)) - ASS->SRT conversion will silently fall back to ASS for ALL files until fixed" "ERROR"
        if ($_assCheck.Error) {
            $_assCheck.Error -split '\r?\n' | Where-Object { $_ -match '\S' } | Select-Object -First 5 |
                ForEach-Object { Write-Log "  $_" "ERROR" }
        }
    } else {
        Write-Log "ass_to_srt import: OK" "DEBUG"
    }
}
if ($script:ShowOverrides.Count -gt 0) {
    Write-Log "Show overrides: $($script:ShowOverrides.Count) pattern(s) configured"
    foreach ($pat in $script:ShowOverrides.Keys) {
        Write-Log "  $pat" "DEBUG"
    }
} else {
    Write-Log "Show overrides: (none configured)"
}
if ($ShowConfig) {
    Write-EffectiveConfigSummary
}
Set-ProgressStage -Stage 'startup' -Status 'Initializing' -Percent $null -SaveNow

if ($ValidateOnly) {
    Write-Log "VALIDATION ONLY: dependency checks and startup validation completed; exiting before scan loop."
    Set-ProgressStage -Stage 'idle' -Status 'Idle' -Percent $null -SaveNow
    Write-Log "PIPELINE SHUTDOWN CLEANLY"
    & $Script:ExitCleanup
    exit 0
}

if ($DrainPendingPushes) {
    Write-Log "DRAIN PENDING PUSHES: forcing upload of parked outputs without scanning sources."
    Set-ProgressStage -Stage 'retry_pending_push' -Status 'Publishing parked outputs' -PushState 'retrying' -Percent $null -SaveNow
    Refresh-PendingPublishIndex | Out-Null
    $pendingPushesRecovered = Invoke-RetryPendingPushes -Force
    Refresh-PendingPublishIndex | Out-Null
    Write-Log "DRAIN PENDING PUSHES: recovered $pendingPushesRecovered file(s); remaining queued: $($script:PendingPublishIndex.Count)"
    Set-ProgressStage -Stage 'idle' -Status 'Idle' -Percent $null -SaveNow
    Write-Log "PIPELINE SHUTDOWN CLEANLY"
    & $Script:ExitCleanup
    exit 0
}

# ==============================================================================
# SINGLE-FILE MODE (Worker dispatch)
# ------------------------------------------------------------------------------
# When -SingleFile is provided the pipeline skips queue discovery entirely
# and encodes exactly one file, then exits.  All existing sidecar, already-
# processed, and failure-state logic still applies — the file is skipped
# with a log message if it would ordinarily be skipped.
#
# This mode is used by the desktop app's Worker dispatcher so that a remote
# worker can process a single coordinator-assigned file without running the
# full scan loop.
# ==============================================================================
if ($SingleFile -ne "") {
    Write-Log "SINGLE-FILE MODE: processing '$SingleFile'"
    $sfPath = $SingleFile.Trim('"').Trim("'")
    if (-not (Test-Path -LiteralPath $sfPath)) {
        Write-Log "ERROR: SingleFile path not found: $sfPath"
        Set-ProgressStage -Stage 'idle' -Status 'Error' -Percent $null -SaveNow
        & $Script:ExitCleanup
        exit 1
    }
    $sfItem = Get-Item -LiteralPath $sfPath
    # Determine media type from configured source roots first. Some queue-backed
    # TV sources use bare episode numbers, so filename pattern matching alone can
    # publish them with movie layout.
    $sfMediaKind = Resolve-SingleFileMediaKind -Path $sfPath -SourceMovies $SourceMovies -SourceTV $SourceTV
    $sfIsTV = [bool]$sfMediaKind.IsTV
    Write-Log "SINGLE-FILE MODE: isTV=$sfIsTV | mediaKind=$($sfMediaKind.MediaKind) | reason=$($sfMediaKind.Reason) | path=$sfPath"
    # Load the processed-output index so Already-Processed can decide whether
    # this file has already been encoded.  Passing an integer (0) here used to
    # crash silently inside Already-Processed when it hit `$idx.TVShows`.
    $sfIndex = Get-ProcessedIndexCached -ForceRefresh:$true
    $sfResult = Invoke-MediaPipelineProcessFile -file $sfItem -isTV:$sfIsTV -idx $sfIndex -QueueIndex 1 -QueueTotal 1 -PriorityInfo $null
    Set-ProgressStage -Stage 'idle' -Status 'Idle' -Percent $null -SaveNow
    $sfStatus = if ($sfResult -and $sfResult.PSObject.Properties['Status']) { [string]$sfResult.Status } else { 'unknown' }
    $sfPublishState = if ($sfResult -and $sfResult.PSObject.Properties['PublishState']) { [string]$sfResult.PublishState } else { '' }
    $sfSuffix = if ([string]::IsNullOrWhiteSpace($sfPublishState)) { '' } else { " publish=$sfPublishState" }
    Write-Log "SINGLE-FILE MODE: complete ($sfStatus$sfSuffix). Exiting."
    & $Script:ExitCleanup
    if ($sfResult -and [bool]$sfResult.Success) { exit 0 }
    exit 1
}

$script:StopRequested = $false
# FIX#5: capture the ReprocessAll setting at startup so we can log the
# auto-disable warning later.
$script:ReprocessAllInitial = $script:ReprocessAll

# Default snapshot location used by the desktop Queue tab. Always written
# during a normal run; also where -EmitQueuePlan writes when the caller
# didn't supply -QueuePlanOutPath.
$queueSnapshotPath = if ($QueuePlanOutPath) {
    $QueuePlanOutPath
} else {
    $script:LocalStateLayout.Paths.QueueSnapshot
}
$enginePlan = New-MediaPipelineEnginePlan `
    -SourceMovies $SourceMovies `
    -SourceTV $SourceTV `
    -QueueSnapshotPath $queueSnapshotPath `
    -Once:$Once `
    -SleepSeconds $SleepSeconds

# -EmitQueuePlan: do exactly one scan + filter pass, write the snapshot,
# and exit. Pending-push retry is intentionally skipped to keep the dry
# run read-only against the network share.
if ($EmitQueuePlan) {
    Invoke-MediaPipelineEmitQueuePlan -EnginePlan $enginePlan | Out-Null
    & $Script:ExitCleanup
    exit 0
}

Invoke-MediaPipelineRun -EnginePlan $enginePlan | Out-Null

Reset-ProgressItemContext
Set-ProgressStage -Stage 'idle' -Status 'Idle' -Percent $null -Route $null -CopyState $null -PushState $null -SidecarState $null -SaveNow
Write-Log "PIPELINE SHUTDOWN CLEANLY"
& $Script:ExitCleanup
