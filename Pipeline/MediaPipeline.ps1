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
    # If the child never launched, $LASTEXITCODE can be $null; exit $null would
    # become exit 0 and mask the failure to a caller/scheduler. Default to 1.
    $childExit = if ($null -ne $LASTEXITCODE) { [int]$LASTEXITCODE } else { 1 }
    exit $childExit
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
        (Join-Path $scriptRoot "MediaPipeline_config.psd1"),
        (Join-Path $scriptRoot "MediaPipeline_config_chatgpt.psd1")
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

# Reserved names a config key must never overwrite: PowerShell preference
# variables (they control error handling / progress / confirmation) and
# automatic variables. Without this guard a config typo such as
# 'ErrorActionPreference = "Continue"' silently disables the pipeline's
# fail-fast behaviour, and a key colliding with a read-only automatic
# variable (e.g. 'PID', 'true') throws and aborts startup under Stop.
$reservedConfigVariableNames = @(
    'ErrorActionPreference','ProgressPreference','VerbosePreference','DebugPreference',
    'WarningPreference','InformationPreference','ConfirmPreference','WhatIfPreference',
    'PSDefaultParameterValues','PSModuleAutoLoadingPreference','OutputEncoding','ErrorView',
    'PSScriptRoot','PSCommandPath','MyInvocation','PSBoundParameters','PSCmdlet','PSItem',
    'args','input','this','Host','ExecutionContext','PWD','HOME','PID','LASTEXITCODE',
    'true','false','null','Error','StackTrace'
)
foreach ($key in $config.Keys) {
    if ($key -in $reservedConfigVariableNames) {
        Add-StartupWarning "Config key '$key' collides with a reserved PowerShell variable and was ignored."
        continue
    }
    $value = $config[$key]
    if ($key -in $arrayKeys) {
        if ($null -eq $value)          { $value = @() }
        elseif ($value -isnot [array]) { $value = @($value) }
    }
    try {
        Set-Variable -Name $key -Value $value -Scope Script
    } catch {
        Add-StartupWarning "Config key '$key' could not be applied as a variable: $($_.Exception.Message)"
    }
}
# Re-assert critical preferences in case the config loop introduced a colliding
# key before the guard above (defence in depth; the denylist should prevent it).
$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'
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
$script:ConvertVobSubToSrt = Get-ConfigBool 'ConvertVobSubToSrt' $false
$script:DropVobSubAfterConversion = Get-ConfigBool 'DropVobSubAfterConversion' $false
$script:TreatVobSubSignsSongsAsForced = Get-ConfigBool 'TreatVobSubSignsSongsAsForced' $false
$script:VobSubOcrToolPath = if ($config.ContainsKey('VobSubOcrToolPath')) { [string]$config['VobSubOcrToolPath'] } else { 'Tools\SubtitleEditLegacy\SubtitleEdit.exe' }
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
$script:VobSubOcrTimeoutSeconds       = Get-ConfigInt 'VobSubOcrTimeoutSeconds' 1800 60 14400
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

if ($config.ContainsKey('VobSubExtractLanguages')) {
    $v = $config['VobSubExtractLanguages']
    if     ($null -eq $v)       { $script:VobSubExtractLanguages = @() }
    elseif ($v -isnot [array])  { $script:VobSubExtractLanguages = @($v) }
    else                         { $script:VobSubExtractLanguages = @($v) }
} else {
    $script:VobSubExtractLanguages = @($SubKeepLanguages)
}
$script:VobSubExtractLanguages = @(
    $script:VobSubExtractLanguages |
        ForEach-Object {
            $text = [string]$_
            if ([string]::IsNullOrWhiteSpace($text)) { 'und' } else { $text.Trim().ToLowerInvariant() }
        } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Select-Object -Unique
)
if ($script:VobSubExtractLanguages.Count -eq 0) {
    $script:VobSubExtractLanguages = @($SubKeepLanguages)
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
    if ($rawAudioBitrate -match '^[1-9]\d*k$') { $rawAudioBitrate } else {
        Add-StartupWarning "Config key 'AudioTranscodeBitrate' should be a positive ffmpeg bitrate like 640k; using default 640k"
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
    if ([string]::IsNullOrWhiteSpace($WorkerResultPath)) {
        Write-Host "FATAL: -WorkerChild requires -WorkerResultPath." -ForegroundColor Red
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
# Declared before the ExitCleanup closure (below) so the closure always
# references a defined variable; the real log mutex is assigned later in the
# LOGGING section.
$logLock = $null
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
$mkvextractPath = Resolve-BundledExecutable -CommandName 'mkvextract' -RelativeCandidates @('Tools\MKVToolNix\mkvextract.exe')

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
$assToSrtCandidates = @(
    (Join-Path $scriptDir "ass_to_srt.py")
)
$assToSrtScript = $assToSrtCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $assToSrtScript) {
    Write-Host "FATAL: ass_to_srt.py not found. Checked: $($assToSrtCandidates -join ', ')" -ForegroundColor Red
    exit 1
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

$progressReadPath = if (Test-Path -LiteralPath $ProgressFile) {
    $ProgressFile
} elseif (Test-Path -LiteralPath $script:LocalStateLayout.LegacyPaths.ProgressFile) {
    $script:LocalStateLayout.LegacyPaths.ProgressFile
} else {
    $null
}
if ($progressReadPath) {
    try {
        $saved = Get-Content -LiteralPath $progressReadPath -Raw | ConvertFrom-Json
        # Coerce each counter defensively: a partially written / truncated
        # progress file can still parse yet be missing fields, which would
        # otherwise leave the counters $null and corrupt later arithmetic
        # and status text. [int]$null and a missing property both yield 0.
        $script:totalProcessed  = [int]($saved.TotalProcessed)
        $script:totalEncoded    = [int]($saved.Encoded)
        $script:totalRemuxed    = [int]($saved.Remuxed)
        $script:totalFailed     = [int]($saved.Failed)
        $script:totalMovies     = [int]($saved.Movies)
        $script:totalTVEpisodes = [int]($saved.TVEpisodes)
        Write-Log "Loaded previous progress: $($script:totalProcessed) files processed"
    } catch { Write-Log "Could not load progress file" "WARN" }
}

$script:SessionBaseline = Get-StatsSnapshot
$script:SessionSkipStats = New-SkipStats
Reset-RoundTracking

# ==============================================================================
# MEDIA PIPELINE ENTRYPOINT SLICES
# ==============================================================================
$mediaPipelineSliceRoot = Join-Path $scriptRoot 'MediaPipeline'
foreach ($slice in @('tx3g_sidecars.ps1', 'remux.ps1', 'encode.ps1')) {
    $slicePath = Join-Path $mediaPipelineSliceRoot $slice
    if (-not (Test-Path -LiteralPath $slicePath)) {
        Write-Host "FATAL: required MediaPipeline slice not found: $slicePath" -ForegroundColor Red
        exit 1
    }
    . $slicePath
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
        $PriorityInfo = $null,
        [string]$LibraryProfileId = ''
    )

    Invoke-MediaPipelineProcessFile -file $file -isTV:$isTV -idx $idx -QueueIndex $QueueIndex -QueueTotal $QueueTotal -PriorityInfo $PriorityInfo -LibraryProfileId $LibraryProfileId
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
$vobSubLanguageText = ($script:VobSubExtractLanguages -join ', ')
$bdpgsOcrToolText = if ($script:BdpgsOcrToolPath) { $script:BdpgsOcrToolPath } else { '(not configured)' }
$vobSubOcrToolText = if ($script:VobSubOcrToolPath) { $script:VobSubOcrToolPath } else { '(not configured)' }
Write-Log ("Convert TX3G  : {0} (languages: {1}; drop original: {2}; external sidecars: {3}; preserve existing SRT: {4})" -f $script:ConvertTx3gToSrt, $tx3gLanguageText, $script:DropTx3gAfterConversion, $script:CreateExternalTx3gSrtSidecars, $script:Tx3gPreserveExistingSrt)
Write-Log ("Convert BDPGS : {0} (languages: {1}; drop original: {2}; OCR tool: {3})" -f $script:ConvertBdpgsToSrt, $bdpgsLanguageText, $script:DropBdpgsAfterConversion, $bdpgsOcrToolText)
Write-Log ("Convert VobSub: {0} (languages: {1}; drop original: {2}; OCR tool: {3})" -f $script:ConvertVobSubToSrt, $vobSubLanguageText, $script:DropVobSubAfterConversion, $vobSubOcrToolText)
Write-Log "Signs/Songs   : keep ASS=$($script:KeepSignsAndSongs) | ASS forced=$($script:TreatAssSignsSongsAsForced) | TX3G forced=$($script:TreatTx3gSignsSongsAsForced) | BDPGS forced=$($script:TreatBdpgsSignsSongsAsForced) | VobSub forced=$($script:TreatVobSubSignsSongsAsForced)"
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
Write-Log "FFmpeg timeouts: encode $($script:FFmpegEncodeTimeoutSeconds)s | encode-cpu $($script:FFmpegCpuEncodeTimeoutSeconds)s | remux $($script:FFmpegRemuxTimeoutSeconds)s | mkvmerge $($script:MkvmergeRemuxTimeoutSeconds)s | subtitle extract $($script:SubtitleExtractTimeoutSeconds)s | subtitle probe $($script:SubtitleProbeTimeoutSeconds)s | BDPGS OCR $($script:BdpgsOcrTimeoutSeconds)s | VobSub OCR $($script:VobSubOcrTimeoutSeconds)s"

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
        if (Test-IsUncPath ([string]$pair.Path)) {
            Write-Log "STARTUP WARNING: $($pair.Label) is a network path; startup reachability probe skipped: $($pair.Path)" "WARN"
            Write-Log "                 Scan/copy phases remain bounded by SourceScanTimeoutSeconds/IndexScanTimeoutSeconds and will report unreachable shares during real work." "WARN"
            continue
        }
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

function Get-MediaPipelineWorkerResultField {
    param(
        $Result,
        [Parameter(Mandatory)] [string] $Name,
        $Default = $null
    )

    if ($Result -and $Result.PSObject.Properties[$Name] -and $null -ne $Result.$Name) {
        return $Result.$Name
    }
    return $Default
}

function Write-MediaPipelineWorkerChildResult {
    param(
        [string] $SourcePath = '',
        $ProcessResult = $null,
        [bool] $IsTV = $false,
        [string] $MediaKind = '',
        [string] $MediaKindReason = '',
        [string] $Status = '',
        [bool] $Success = $false,
        [string] $Reason = '',
        [string] $ErrorCode = '',
        [string] $Route = '',
        [string] $PublishState = ''
    )

    if (-not $WorkerChild -or [string]::IsNullOrWhiteSpace($WorkerResultPath)) {
        return
    }

    $statusText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'Status' -Default $Status)
    if ([string]::IsNullOrWhiteSpace($statusText)) { $statusText = 'unknown' }
    $successValue = [bool](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'Success' -Default $Success)
    $reasonText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'Reason' -Default $Reason)
    $errorCodeText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'ErrorCode' -Default $ErrorCode)
    $sourcePathText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'SourcePath' -Default $SourcePath)
    $sourceNameText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'SourceName' -Default ([System.IO.Path]::GetFileName($sourcePathText)))
    $routeText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'Route' -Default $Route)
    $routeReasonCodeText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'RouteReasonCode' -Default '')
    $routeReasonText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'RouteReason' -Default '')
    $publishStateText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'PublishState' -Default $PublishState)
    $publishModeText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'PublishMode' -Default '')
    $outputPathText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'OutputPath' -Default '')
    $outputSizeBytes = 0L
    try {
        $outputSizeBytes = [long](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'OutputSizeBytes' -Default 0)
    } catch {
        $outputSizeBytes = 0L
    }

    $payload = [ordered]@{
        SchemaVersion       = 'local_worker_result.v1'
        Success             = $successValue
        Status              = $statusText
        Reason              = $reasonText
        ErrorCode           = $errorCodeText
        SourcePath          = $sourcePathText
        SourceName          = $sourceNameText
        IsTV                = [bool]$IsTV
        MediaKind           = [string]$MediaKind
        MediaKindReason     = [string]$MediaKindReason
        Route               = $routeText
        RouteReasonCode     = $routeReasonCodeText
        RouteReason         = $routeReasonText
        PublishState        = $publishStateText
        PublishMode         = $publishModeText
        OutputPath          = $outputPathText
        OutputSizeBytes     = $outputSizeBytes
        WorkerSlotId        = [int]$WorkerSlotId
        WorkerRunId         = [string]$WorkerRunId
        WorkerClaimId       = [string]$WorkerClaimId
        CompletedAt         = (Get-Date).ToString('o')
    }

    try {
        Write-MediaPipelineJsonAtomic -Path $WorkerResultPath -InputObject $payload -Depth 10 | Out-Null
        Write-Log "WORKER CHILD: wrote result status=$statusText success=$successValue path=$WorkerResultPath" 'DEBUG'
    } catch {
        Write-Log "WORKER CHILD: failed to write result to $WorkerResultPath`: $_" 'ERROR'
    }
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
        Write-MediaPipelineWorkerChildResult `
            -SourcePath $sfPath `
            -Status 'failed' `
            -Success:$false `
            -Reason 'SingleFile path not found'
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
    Write-MediaPipelineWorkerChildResult `
        -SourcePath $sfPath `
        -ProcessResult $sfResult `
        -IsTV:$sfIsTV `
        -MediaKind ([string]$sfMediaKind.MediaKind) `
        -MediaKindReason ([string]$sfMediaKind.Reason)
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
$pipelineScriptPath = if (-not [string]::IsNullOrWhiteSpace($PSCommandPath)) {
    [string]$PSCommandPath
} elseif ($MyInvocation.MyCommand.Path) {
    [string]$MyInvocation.MyCommand.Path
} else {
    Join-Path $pipelineRoot 'MediaPipeline.ps1'
}
$currentPowerShellPath = ''
try {
    $currentPowerShellPath = [string][System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
} catch {
    $currentPowerShellPath = ''
}
if ([string]::IsNullOrWhiteSpace($currentPowerShellPath)) {
    $pwshCommand = Get-Command pwsh.exe -ErrorAction SilentlyContinue
    if (-not $pwshCommand) {
        $pwshCommand = Get-Command pwsh -ErrorAction SilentlyContinue
    }
    if ($pwshCommand -and $pwshCommand.Source) {
        $currentPowerShellPath = [string]$pwshCommand.Source
    }
}
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
    -SleepSeconds $SleepSeconds `
    -ScriptPath $pipelineScriptPath `
    -ConfigPath $configPath `
    -PowerShellPath $currentPowerShellPath `
    -ParallelEncodeMode ([string]$script:ParallelEncodeMode) `
    -MaxParallelEncodes ([int]$script:MaxParallelEncodes)

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
