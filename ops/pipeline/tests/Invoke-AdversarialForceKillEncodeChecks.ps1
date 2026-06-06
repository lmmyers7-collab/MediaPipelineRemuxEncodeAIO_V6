[CmdletBinding()]
param(
    [int] $TimeoutSeconds = 150,
    [switch] $KeepWorkRoot
)

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent $testsRoot
$projectRoot = Split-Path -Parent $pipelineRoot

$bundledPwshPath = Join-Path $pipelineRoot 'PowerShell-7.6.0-win-x64\pwsh.exe'
$ffmpegPath = Join-Path $pipelineRoot 'Tools\ffmpeg\bin\ffmpeg.exe'
$ffprobePath = Join-Path $pipelineRoot 'Tools\ffmpeg\bin\ffprobe.exe'

$missingTools = @()
foreach ($tool in @(
    @{ Name = 'PowerShell'; Path = $bundledPwshPath },
    @{ Name = 'ffmpeg';     Path = $ffmpegPath },
    @{ Name = 'ffprobe';    Path = $ffprobePath }
)) {
    if (-not (Test-Path -LiteralPath $tool.Path -PathType Leaf)) {
        $missingTools += "$($tool.Name) ($($tool.Path))"
    }
}

if ($missingTools.Count -gt 0) {
    Write-Host ("SKIP: adversarial force-kill encode checks require: {0}" -f ($missingTools -join ', '))
    return
}

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Invoke-SmokeCommand {
    param(
        [Parameter(Mandatory)] [string] $FilePath,
        [Parameter(Mandatory)] [string[]] $ArgumentList,
        [Parameter(Mandatory)] [string] $Label
    )

    $output = & $FilePath @ArgumentList 2>&1 | ForEach-Object { [string]$_ }
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "$Label failed with exit $exitCode`n$($output -join [Environment]::NewLine)"
    }
    return @($output)
}

function ConvertTo-Psd1Literal {
    param($Value)

    if ($null -eq $Value) { return '$null' }
    if ($Value -is [bool]) { return $(if ($Value) { '$true' } else { '$false' }) }
    if ($Value -is [int] -or $Value -is [long] -or $Value -is [double] -or $Value -is [decimal]) {
        return ([string]$Value)
    }
    if ($Value -is [System.Collections.IDictionary]) {
        $items = foreach ($key in $Value.Keys) {
            "        $key = $(ConvertTo-Psd1Literal -Value $Value[$key])"
        }
        return "@{`n$($items -join [Environment]::NewLine)`n    }"
    }
    if ($Value -is [array]) {
        $items = @($Value | ForEach-Object { ConvertTo-Psd1Literal -Value $_ })
        return '@(' + ($items -join ', ') + ')'
    }
    $escaped = ([string]$Value) -replace "'", "''"
    return "'$escaped'"
}

function Write-SmokeConfig {
    param(
        [Parameter(Mandatory)] [hashtable] $Config,
        [Parameter(Mandatory)] [string] $Path
    )

    $orderedKeys = @($Config.Keys | Sort-Object)
    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add('@{')
    foreach ($key in $orderedKeys) {
        $lines.Add("    $key = $(ConvertTo-Psd1Literal -Value $Config[$key])")
    }
    $lines.Add('}')
    [System.IO.File]::WriteAllText($Path, ($lines -join [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
}

function Test-FFmpegEncoderAvailable {
    param([Parameter(Mandatory)] [string] $EncoderName)

    $encoders = Invoke-SmokeCommand -FilePath $ffmpegPath -Label 'ffmpeg encoder inventory' -ArgumentList @(
        '-hide_banner',
        '-encoders'
    )
    return (($encoders -join "`n") -match ("(?im)\b" + [regex]::Escape($EncoderName) + "\b"))
}

function New-ForceKillSmokeVideo {
    param([Parameter(Mandatory)] [string] $Path)

    $args = @(
        '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'lavfi', '-i', 'testsrc2=size=960x540:rate=24:duration=300',
        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100:duration=300',
        '-shortest',
        '-c:v', 'mpeg4',
        '-q:v', '5',
        '-c:a', 'aac',
        $Path
    )
    Invoke-SmokeCommand -FilePath $ffmpegPath -ArgumentList $args -Label "generate $Path" | Out-Null
    Assert-True ((Test-Path -LiteralPath $Path -PathType Leaf) -and ((Get-Item -LiteralPath $Path).Length -gt 0)) "failed to generate smoke media: $Path"
}

function Get-ChildProcessIds {
    param([Parameter(Mandatory)] [int] $ParentProcessId)

    try {
        return @(
            Get-CimInstance Win32_Process -Filter "ParentProcessId = $ParentProcessId" -ErrorAction Stop |
                ForEach-Object { [int]$_.ProcessId }
        )
    } catch {
        return @()
    }
}

function Stop-ProcessTree {
    param([Parameter(Mandatory)] [int] $RootProcessId)

    $visited = [System.Collections.Generic.HashSet[int]]::new()
    $ordered = [System.Collections.Generic.List[int]]::new()

    function Add-ProcessTreeId {
        param([int] $ProcessId)
        if (-not $visited.Add($ProcessId)) { return }
        foreach ($childId in (Get-ChildProcessIds -ParentProcessId $ProcessId)) {
            Add-ProcessTreeId -ProcessId $childId
        }
        $ordered.Add($ProcessId)
    }

    Add-ProcessTreeId -ProcessId $RootProcessId

    foreach ($processId in $ordered) {
        try {
            $process = Get-Process -Id $processId -ErrorAction Stop
            Stop-Process -InputObject $process -Force -ErrorAction SilentlyContinue
        } catch {}
    }
    foreach ($processId in $ordered) {
        try { Wait-Process -Id $processId -Timeout 10 -ErrorAction SilentlyContinue } catch {}
    }
}

function Get-TailText {
    param([string] $Path, [int] $Lines = 60)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return '' }
    return ((Get-Content -LiteralPath $Path -Tail $Lines -ErrorAction SilentlyContinue) -join [Environment]::NewLine)
}

function Get-AdversarialDiagnostics {
    param(
        [string] $WorkRoot,
        [string] $StdoutPath,
        [string] $StderrPath,
        [string] $ProgressPath,
        [string] $EventPath
    )

    $parts = [System.Collections.Generic.List[string]]::new()
    $parts.Add("work root: $WorkRoot")
    $parts.Add("stdout tail:`n$(Get-TailText -Path $StdoutPath)")
    $parts.Add("stderr tail:`n$(Get-TailText -Path $StderrPath)")
    $parts.Add("progress:`n$(Get-TailText -Path $ProgressPath -Lines 20)")
    $parts.Add("events tail:`n$(Get-TailText -Path $EventPath)")
    return ($parts -join ([Environment]::NewLine + '---' + [Environment]::NewLine))
}

function Assert-NoAcceptedOutput {
    param(
        [Parameter(Mandatory)] [string] $Outsource,
        [Parameter(Mandatory)] [string] $LocalBase,
        [Parameter(Mandatory)] [string] $SourcePath
    )

    $publishedFiles = @(Get-ChildItem -LiteralPath $Outsource -Recurse -File -ErrorAction SilentlyContinue)
    Assert-True ($publishedFiles.Count -eq 0) "force-kill smoke accepted files in Outsource: $($publishedFiles.FullName -join ', ')"

    $localEncoded = Join-Path $LocalBase 'Encoded'
    $localOutputs = @(Get-ChildItem -LiteralPath $localEncoded -Recurse -File -ErrorAction SilentlyContinue)
    Assert-True ($localOutputs.Count -eq 0) "force-kill smoke accepted local encoded files: $($localOutputs.FullName -join ', ')"

    $completedManifestCandidates = @(
        (Join-Path $LocalBase 'State\Completed\completed_jobs.jsonl'),
        (Join-Path $LocalBase 'Completed\completed_jobs.jsonl')
    )
    foreach ($manifestPath in $completedManifestCandidates) {
        if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { continue }
        $manifestText = Get-Content -LiteralPath $manifestPath -Raw
        Assert-True ([string]::IsNullOrWhiteSpace($manifestText)) "completed manifest was written after force-kill: $manifestPath"
    }

    $pendingRoots = @(
        (Join-Path $LocalBase 'State\PendingServerPush'),
        (Join-Path $LocalBase 'PendingServerPush')
    )
    foreach ($pendingRoot in $pendingRoots) {
        if (-not (Test-Path -LiteralPath $pendingRoot -PathType Container)) { continue }
        $pendingFiles = @(Get-ChildItem -LiteralPath $pendingRoot -Recurse -File -ErrorAction SilentlyContinue)
        Assert-True ($pendingFiles.Count -eq 0) "pending publish state was written after force-kill: $($pendingFiles.FullName -join ', ')"
    }

    $eventLog = Join-Path $LocalBase 'State\Progress\pipeline_events.jsonl'
    if (Test-Path -LiteralPath $eventLog -PathType Leaf) {
        $eventText = Get-Content -LiteralPath $eventLog -Raw
        Assert-True ($eventText -notmatch '"event_type":"job_completed"') 'pipeline event log contains job_completed after force-kill'
        Assert-True ($eventText -notmatch [regex]::Escape($SourcePath) -or $eventText -notmatch '"publish_') 'pipeline event log contains publish event text for the force-killed source'
    }
}

. (Join-Path $projectRoot 'ops\pipeline\engine\config\config_schema.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\shared\media_constants.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\shared\failure_codes.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\decide\encode_policy.ps1')

if (-not (Test-FFmpegEncoderAvailable -EncoderName 'libx265')) {
    Write-Host 'SKIP: adversarial force-kill encode checks require bundled ffmpeg libx265 encoder support.'
    return
}

$workRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-force-kill-encode-" + [guid]::NewGuid().ToString('N'))
$sourceMovies = Join-Path $workRoot 'SourceMovies'
$sourceTv = Join-Path $workRoot 'SourceTV'
$outsource = Join-Path $workRoot 'Outsource'
$localBase = Join-Path $workRoot 'LocalBase'
$processingDir = Join-Path $localBase 'Incoming\Processing'
$configPath = Join-Path $workRoot 'force_kill_config.psd1'
$queueBeforePath = Join-Path $workRoot 'queue_before.json'
$queueAfterPath = Join-Path $workRoot 'queue_after.json'
$stdoutPath = Join-Path $workRoot 'pipeline_stdout.txt'
$stderrPath = Join-Path $workRoot 'pipeline_stderr.txt'
$progressPath = Join-Path $localBase 'State\Progress\pipeline_progress.json'
$eventPath = Join-Path $localBase 'State\Progress\pipeline_events.jsonl'
$sourcePath = Join-Path $sourceMovies 'Force.Kill.Encode.2026.mp4'
$previousMutexSuffix = $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX
$hadPreviousMutexSuffix = Test-Path Env:\MEDIA_PIPELINE_TEST_MUTEX_SUFFIX
$pipelineProcess = $null
$smokeSucceeded = $false

try {
    $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = [guid]::NewGuid().ToString('N')
    New-Item -ItemType Directory -Path $sourceMovies, $sourceTv, $outsource, $localBase -Force | Out-Null

    New-ForceKillSmokeVideo -Path $sourcePath
    $sourceHashBefore = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash

    $config = [hashtable](Get-MediaPipelineConfigDefaultValues)
    $config['SourceMovies'] = $sourceMovies
    $config['SourceTV'] = $sourceTv
    $config['Outsource'] = $outsource
    $config['LocalBase'] = $localBase
    foreach ($profile in @($config['LibraryProfiles'])) {
        $designation = ([string]$profile['designation']).Trim().ToLowerInvariant()
        if ($designation -eq 'movie') {
            $profile['source_path'] = $sourceMovies
        } elseif ($designation -eq 'tv') {
            $profile['source_path'] = $sourceTv
        }
        $profile['output_path'] = $outsource
        $profile['promotion_enabled'] = $false
        $profile['promotion_destination'] = ''
    }
    $config['MovieRoute1080pTargetSizeGB'] = 999
    $config['MovieRoute1440pTargetSizeGB'] = 999
    $config['MovieRoute4KTargetSizeGB'] = 999
    $config['TVRoute1080pTargetSizeGB'] = 999
    $config['TVRoute1440pTargetSizeGB'] = 999
    $config['TVRoute4KTargetSizeGB'] = 999
    $config['MinFreeSpaceGB'] = 1
    $config['OutsourceMinFreeSpaceGB'] = 1
    $config['DeferredPublish'] = $false
    $config['RemuxSafeVideoCodecs'] = @('hevc','h265','h.265')
    $config['CompatibleAudioCodecs'] = @('aac','ac3','eac3')
    # Keep the fixture schema-valid while still preferring the hardware-first
    # encoder path that falls back to CPU on hosts without usable NVENC support.
    $config['VideoCodec'] = 'hevc_nvenc'
    $config['VideoPreset'] = 'p7'
    $config['VideoQuality'] = 22
    $config['FallbackCpuQuality'] = 20
    $config['CpuEncodePreset'] = 'medium'
    $config['CpuEncodeMaxThreads'] = 1
    $config['CpuEncodeProcessPriority'] = 'BelowNormal'
    $config['OutputContainer'] = 'mkv'
    $config['SizeGuardMode'] = 'advisory'
    $config['OutputSizeMultiplier'] = 1.1
    $config['SkipStabilityCheck'] = $true
    $config['FileStabilityWait'] = 0
    $config['EnableIntegrityCheck'] = $false
    $config['ConvertTx3gToSrt'] = $false
    $config['DropTx3gAfterConversion'] = $false
    $config['CreateExternalTx3gSrtSidecars'] = $false
    $config['ConvertBdpgsToSrt'] = $false
    $config['DropBdpgsAfterConversion'] = $false
    $config['BdpgsOcrToolPath'] = ''
    $config['BdpgsOcrTessdataPath'] = ''
    $config['RobocopyFlags'] = @('/R:1','/W:1','/NP','/NDL','/NFL')
    $config['RobocopyTimeoutSeconds'] = 60
    $config['FFmpegEncodeTimeoutSeconds'] = 120
    $config['FFmpegCpuEncodeTimeoutSeconds'] = 900
    $config['FFmpegRemuxTimeoutSeconds'] = 120
    $config['SubtitleExtractTimeoutSeconds'] = 60
    $config['SubtitleProbeTimeoutSeconds'] = 15
    $config['SourceScanTimeoutSeconds'] = 60
    $config['IndexScanTimeoutSeconds'] = 60
    $config['CleanupScanTimeoutSeconds'] = 30
    $config['ProcessedIndexRefreshSeconds'] = 1
    $config['SourceScanIntervalSeconds'] = 1
    $config['CleanupRemoteStaging'] = $true
    $config['ConsoleLogLevel'] = 'ERROR'
    $config['FileLogLevel'] = 'DEBUG'
    Write-SmokeConfig -Config $config -Path $configPath

    Invoke-SmokeCommand -FilePath $bundledPwshPath -Label 'pipeline queue plan before force-kill' -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', (Join-Path $pipelineRoot 'MediaPipeline.ps1'),
        '-ConfigPath', $configPath,
        '-EmitQueuePlan',
        '-QueuePlanOutPath', $queueBeforePath
    ) | Out-Null
    $queueBefore = Get-Content -LiteralPath $queueBeforePath -Raw | ConvertFrom-Json -ErrorAction Stop
    $sourceRowsBefore = @($queueBefore.rows | Where-Object { [string]$_.source_path -eq $sourcePath })
    Assert-True ($sourceRowsBefore.Count -eq 1) "source missing from queue plan before force-kill: $($queueBefore | ConvertTo-Json -Depth 6)"
    $routeBefore = [string]$sourceRowsBefore[0].route
    Assert-True ($routeBefore -in @('encode', 'REMUX (codec check pending)')) "force-kill source did not have backend route evidence before processing: $($sourceRowsBefore[0] | ConvertTo-Json -Depth 6)"
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$sourceRowsBefore[0].route_reason_code)) 'queue plan before force-kill did not include backend route evidence'

    $pipelineArgs = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', (Join-Path $pipelineRoot 'MediaPipeline.ps1'),
        '-ConfigPath', $configPath,
        '-Once'
    )
    $pipelineProcess = Start-Process -FilePath $bundledPwshPath -ArgumentList $pipelineArgs -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath

    $deadline = (Get-Date).AddSeconds([math]::Max(30, $TimeoutSeconds))
    $observedPartial = $null
    $observedPartialPath = ''
    while ((Get-Date) -lt $deadline) {
        if ($pipelineProcess.HasExited) {
            $diagnostics = Get-AdversarialDiagnostics -WorkRoot $workRoot -StdoutPath $stdoutPath -StderrPath $stderrPath -ProgressPath $progressPath -EventPath $eventPath
            throw "pipeline exited before an active encode partial was observed (exit $($pipelineProcess.ExitCode))`n$diagnostics"
        }

        $partials = @(Get-ChildItem -LiteralPath $processingDir -Filter 'encode_temp*.mkv' -File -ErrorAction SilentlyContinue)
        if ($partials.Count -gt 0) {
            $observedPartial = $partials | Select-Object -First 1
            $observedPartialPath = [string]$observedPartial.FullName
            Start-Sleep -Seconds 10
            try { $pipelineProcess.Refresh() } catch {}
            if ($pipelineProcess.HasExited) {
                $diagnostics = Get-AdversarialDiagnostics -WorkRoot $workRoot -StdoutPath $stdoutPath -StderrPath $stderrPath -ProgressPath $progressPath -EventPath $eventPath
                throw "pipeline exited during encode-partial grace period (exit $($pipelineProcess.ExitCode))`n$diagnostics"
            }
            break
        }

        Start-Sleep -Milliseconds 500
        try { $pipelineProcess.Refresh() } catch {}
    }

    if (-not $observedPartial) {
        $diagnostics = Get-AdversarialDiagnostics -WorkRoot $workRoot -StdoutPath $stdoutPath -StderrPath $stderrPath -ProgressPath $progressPath -EventPath $eventPath
        throw "timed out waiting for an active encode partial`n$diagnostics"
    }

    Write-Host "Observed active encode partial: $observedPartialPath"
    Stop-ProcessTree -RootProcessId ([int]$pipelineProcess.Id)
    try { $pipelineProcess.Refresh() } catch {}
    Assert-True ($pipelineProcess.HasExited) "pipeline process was not force-killed: PID $($pipelineProcess.Id)"

    $partialAfterKill = Get-Item -LiteralPath $observedPartialPath -ErrorAction SilentlyContinue
    Assert-True ($null -ne $partialAfterKill) "observed encode temp output disappeared before post-kill assertions: $observedPartialPath"
    Assert-True ([long]$partialAfterKill.Length -gt 0) "observed encode temp output did not contain bytes after force-kill: $observedPartialPath"
    Write-Host "Post-kill partial size: $($partialAfterKill.Length) bytes"

    $sourceHashAfterKill = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
    Assert-True ($sourceHashAfterKill -eq $sourceHashBefore) 'source hash changed after force-killing active encode'
    Assert-NoAcceptedOutput -Outsource $outsource -LocalBase $localBase -SourcePath $sourcePath

    Invoke-SmokeCommand -FilePath $bundledPwshPath -Label 'pipeline queue plan after force-kill' -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', (Join-Path $pipelineRoot 'MediaPipeline.ps1'),
        '-ConfigPath', $configPath,
        '-EmitQueuePlan',
        '-QueuePlanOutPath', $queueAfterPath
    ) | Out-Null
    $queueAfter = Get-Content -LiteralPath $queueAfterPath -Raw | ConvertFrom-Json -ErrorAction Stop
    $sourceRowsAfter = @($queueAfter.rows | Where-Object { [string]$_.source_path -eq $sourcePath })
    Assert-True ($sourceRowsAfter.Count -eq 1) "source missing from queue plan after force-kill: $($queueAfter | ConvertTo-Json -Depth 6)"
    $routeAfter = [string]$sourceRowsAfter[0].route
    Assert-True ($routeAfter -in @('encode', 'REMUX (codec check pending)')) "source was not still backend-planned for processing after force-kill: $($sourceRowsAfter[0] | ConvertTo-Json -Depth 6)"
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$sourceRowsAfter[0].route_reason_code)) 'queue plan after force-kill did not include backend route evidence'

    $sourceHashAfterQueuePlan = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
    Assert-True ($sourceHashAfterQueuePlan -eq $sourceHashBefore) 'source hash changed after post-kill queue planning'
    Assert-NoAcceptedOutput -Outsource $outsource -LocalBase $localBase -SourcePath $sourcePath

    $remainingPartials = @(Get-ChildItem -LiteralPath $processingDir -Filter 'encode_temp*.mkv' -File -ErrorAction SilentlyContinue)
    Write-Host "PASS: force-killed encode was not accepted as complete; source remained queued. Remaining processing temp files: $($remainingPartials.Count)"
    $smokeSucceeded = $true
} finally {
    if ($pipelineProcess -and -not $pipelineProcess.HasExited) {
        Stop-ProcessTree -RootProcessId ([int]$pipelineProcess.Id)
    }

    if ($hadPreviousMutexSuffix) {
        $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = $previousMutexSuffix
    } else {
        Remove-Item Env:\MEDIA_PIPELINE_TEST_MUTEX_SUFFIX -ErrorAction SilentlyContinue
    }

    if ($smokeSucceeded -and -not $KeepWorkRoot -and -not $env:MEDIA_PIPELINE_KEEP_FAILED_SMOKE) {
        $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
        $resolvedWorkRoot = [System.IO.Path]::GetFullPath($workRoot)
        if ($resolvedWorkRoot.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "Work root retained: $workRoot"
    }
}
