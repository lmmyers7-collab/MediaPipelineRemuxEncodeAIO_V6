# ==============================================================================
# MEDIA PIPELINE — entrypoint / composition root
# ==============================================================================
<#
.SYNOPSIS
    Entry script for the remux/encode/publish media pipeline.

.DESCRIPTION
    Thin orchestrator. Resolves the config, dot-sources the engine modules
    (ops/pipeline/engine/<domain>/*.ps1) and the entrypoint slices (./MediaPipeline/*.ps1)
    into this script scope so they share $script: state, validates dependencies and
    startup paths, then dispatches exactly one run mode. All media/domain behaviour lives
    in the engine modules and slices; this file only sequences startup and selects a mode.

    Run modes (parameters):
      (default)                         continuous scan loop
      -Once                             one scan pass then exit
      -DrainPendingPushes               publish parked outputs only, no scan
      -SingleFile <path>                worker dispatch: process exactly one file
      -EmitQueuePlan                    write the queue snapshot and exit (dry run)
      -ValidateOnly                     dependency + startup checks then exit
      -ShowConfig                       print the resolved effective config
      -DumpEffectiveConfigPath <path>   write the resolved-config JSON oracle and exit

.NOTES
    Platform: Windows, PowerShell 7+ (auto-relaunches if started under 5.x).
    High-risk areas (FFmpeg, subtitles, audio, publish/pending-publish, queue, settings)
    are governed by AGENTS.md section 7 and docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md.
    The historical [FIX#N] change notes that used to fill this header were removed on
    2026-06-05; that detail remains in git history and CHANGELOG.md.
#>

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
    [string]$WorkerResultPath = "",

    # Diagnostic: resolve config + derived runtime settings, write a complete
    # JSON dump of them to this path, and exit before the scan loop. Read-only
    # (no singleton lock, no media work). Used as a parity oracle for config
    # refactors and as operator "what did this run resolve" diagnostics.
    [string]$DumpEffectiveConfigPath = ""
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
# ==============================================================================
$pipelineRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$repoRootForModules = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $pipelineRoot))
$moduleRoot = Join-Path $pipelineRoot 'Modules'
# Engine module manifest + ordered dot-source loader (see MediaPipeline/module_loader.ps1).
$moduleLoaderSlice = Join-Path $pipelineRoot 'MediaPipeline\module_loader.ps1'
if (-not (Test-Path -LiteralPath $moduleLoaderSlice)) {
    Write-Host "FATAL: required loader not found: $moduleLoaderSlice" -ForegroundColor Red
    exit 1
}
. $moduleLoaderSlice

# ==============================================================================
# CONFIGURATION
# ==============================================================================
$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$configRoot = Join-Path $repoRootForModules 'ops\pipeline\config'
$configCandidates = if ($ConfigPath) {
    $candidate = if ([System.IO.Path]::IsPathRooted($ConfigPath)) {
        $ConfigPath
    } else {
        Join-Path (Get-Location).Path $ConfigPath
    }
    @($candidate)
} else {
    @(
        (Join-Path $configRoot "MediaPipeline_config.psd1"),
        (Join-Path $configRoot "MediaPipeline_config_chatgpt.psd1"),
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

Initialize-MediaPipelineRuntimeConfig -Config $config -SchemaResult $configSchemaCheck
# Re-assert critical preferences at script scope after config resolution
# (defence in depth; the reserved-name denylist inside the initializer already
# prevents a config key from clobbering them).
$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'
# Derived runtime paths + state layout (+ worker-child slot override). See MediaPipeline/runtime_paths.ps1.
$bootSlice = Join-Path $pipelineRoot 'MediaPipeline\runtime_paths.ps1'
if (-not (Test-Path -LiteralPath $bootSlice)) { Write-Host "FATAL: required slice not found: $bootSlice" -ForegroundColor Red; exit 1 }
. $bootSlice

# ==============================================================================
# SINGLE INSTANCE LOCK — named OS Mutex (eliminates TOCTOU race from file+PID)
# ==============================================================================
$mutexSuffix = ''
if (-not [string]::IsNullOrWhiteSpace($env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX)) {
    $mutexSuffix = '_' + (($env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX) -replace '[^A-Za-z0-9_.-]', '_')
}
$instanceMutexName = "Global\MediaPipelineSingleInstance$mutexSuffix"
$instanceMutex  = $null
$instanceLocked = $false
$workerSlotMutex = $null
$workerSlotLocked = $false
# Declared before the ExitCleanup closure (below) so the closure always
# references a defined variable; the real log mutex is assigned later in the
# LOGGING section.
$logLock = $null
if (-not $ValidateOnly -and -not $WorkerChild -and -not $DumpEffectiveConfigPath) {
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

$ffmpegPath   = Resolve-BundledExecutable -CommandName 'ffmpeg'   -RelativeCandidates @('..\tools\ffmpeg\bin\ffmpeg.exe', 'Tools\ffmpeg\bin\ffmpeg.exe')
$ffprobePath  = Resolve-BundledExecutable -CommandName 'ffprobe'  -RelativeCandidates @('..\tools\ffmpeg\bin\ffprobe.exe', 'Tools\ffmpeg\bin\ffprobe.exe')
$mkvmergePath = Resolve-BundledExecutable -CommandName 'mkvmerge' -RelativeCandidates @('..\tools\MKVToolNix\mkvmerge.exe', 'Tools\MKVToolNix\mkvmerge.exe')
$mkvextractPath = Resolve-BundledExecutable -CommandName 'mkvextract' -RelativeCandidates @('..\tools\MKVToolNix\mkvextract.exe', 'Tools\MKVToolNix\mkvextract.exe')

if (-not $ffmpegPath -or -not $ffprobePath) {
    Write-Host "FATAL: bundled ffmpeg/ffprobe not found in ops\\pipeline\\tools\\ffmpeg\\bin. Set AllowSystemTools=true only for development fallback." -ForegroundColor Red; exit 1
}
if (-not $mkvmergePath) {
    Write-Host "FATAL: bundled mkvmerge not found in ops\\pipeline\\tools\\MKVToolNix. Set AllowSystemTools=true only for development fallback." -ForegroundColor Red; exit 1
}
if (-not (Get-Command robocopy -ErrorAction SilentlyContinue)) {
    Write-Host "FATAL: robocopy not found" -ForegroundColor Red; exit 1
}

# Python + pysubs2 check — subtitle conversion depends on these.
# Fail fast here rather than silently producing files with no subtitles.
$pythonPath = Resolve-BundledExecutable -CommandName 'python' -RelativeCandidates @(
    '..\runtime\Python\python.exe',
    '..\..\..\apps\desktop\runtime\Python\python.exe',
    'Runtime\Python\python.exe',
    '..\apps\desktop\runtime\Python\python.exe',
    'Tools\Python\python.exe'
)
if (-not $pythonPath) {
    Write-Host "FATAL: bundled python not found in ops\\pipeline\\runtime\\Python, apps\\desktop\\runtime\\Python, or Tools\\Python. Set AllowSystemTools=true only for development fallback." -ForegroundColor Red; exit 1
}
$sourcePythonPath = Join-Path $repoRootForModules 'src'
if (Test-Path -LiteralPath $sourcePythonPath) {
    $oldPythonPath = [string]$env:PYTHONPATH
    $pathSeparator = [string][System.IO.Path]::PathSeparator
    if ([string]::IsNullOrWhiteSpace($oldPythonPath)) {
        $env:PYTHONPATH = $sourcePythonPath
    } elseif (-not (@($oldPythonPath -split [regex]::Escape($pathSeparator)) -contains $sourcePythonPath)) {
        $env:PYTHONPATH = "$sourcePythonPath$pathSeparator$oldPythonPath"
    }
}
$null = & $pythonPath -c "import pysubs2" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "FATAL: pysubs2 not installed. Run: pip install pysubs2" -ForegroundColor Red; exit 1
}

# Validate the Python helper script exists next to this script
$assToSrtCandidates = @(
    (Join-Path $repoRootForModules "src\mediapipeline\pipeline\ass_to_srt_cli.py"),
    (Join-Path $scriptDir "ass_to_srt.py")
)
$assToSrtScript = $assToSrtCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $assToSrtScript) {
    Write-Host "FATAL: ASS-to-SRT helper not found. Checked: $($assToSrtCandidates -join ', ')" -ForegroundColor Red
    exit 1
}

# ==============================================================================
# LOGGING
# ==============================================================================
# Keep a stable mutex name so desktop/pipeline launches serialize access to the same log file.
$logMutexName = "MediaPipelineLogMutex$mutexSuffix"
$logLock = [System.Threading.Mutex]::new($false, $logMutexName)

# ==============================================================================
# STARTUP — directories first, then clean temp files
# ==============================================================================
$bootSlice = Join-Path $pipelineRoot 'MediaPipeline\startup_filesystem.ps1'
if (-not (Test-Path -LiteralPath $bootSlice)) { Write-Host "FATAL: required slice not found: $bootSlice" -ForegroundColor Red; exit 1 }
. $bootSlice

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
# SESSION STATE / PROGRESS COUNTERS (Initialize-MediaPipelineSessionState)
# ==============================================================================
Initialize-MediaPipelineSessionState

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
# PROCESSING HELPERS
# ==============================================================================
# Process-File remains available through ops\pipeline\engine\process\file_processor.ps1.
# Worker child result serialization lives in ops\pipeline\engine\process\worker_result.ps1.
# Queue snapshot helpers live in ops\pipeline\engine\queue\pipeline_engine.ps1.

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

# Log the resolved run mode + effective config, then probe NVENC.
Write-MediaPipelineStartupConfigLog

# ==============================================================================
# STARTUP PATH VALIDATION  (see MediaPipeline/startup_path_validation.ps1)
# ==============================================================================
$bootSlice = Join-Path $pipelineRoot 'MediaPipeline\startup_path_validation.ps1'
if (-not (Test-Path -LiteralPath $bootSlice)) { Write-Host "FATAL: required slice not found: $bootSlice" -ForegroundColor Red; exit 1 }
. $bootSlice

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
if ($DumpEffectiveConfigPath) {
    try {
        $effectiveDump = Get-MediaPipelineResolvedConfigDump
        ($effectiveDump | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $DumpEffectiveConfigPath -Encoding UTF8 -Force
        Write-Log "Effective config dumped to $DumpEffectiveConfigPath"
        Set-ProgressStage -Stage 'idle' -Status 'Idle' -Percent $null -SaveNow
        & $Script:ExitCleanup
        exit 0
    } catch {
        Write-Log "Failed to dump effective config to $DumpEffectiveConfigPath : $_" "ERROR"
        & $Script:ExitCleanup
        exit 1
    }
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
