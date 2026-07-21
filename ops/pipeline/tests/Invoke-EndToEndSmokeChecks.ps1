[CmdletBinding()]
param(
    [switch]$AllowMissingTools
)

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent $testsRoot
$opsRoot = Split-Path -Parent $pipelineRoot
$projectRoot = Split-Path -Parent $opsRoot

$bundledPwshPath = Join-Path $pipelineRoot 'runtime\PowerShell-7.6.0-win-x64\pwsh.exe'
$ffmpegPath = Join-Path $pipelineRoot 'tools\ffmpeg\bin\ffmpeg.exe'
$ffprobePath = Join-Path $pipelineRoot 'tools\ffmpeg\bin\ffprobe.exe'
$mediaPipelineScript = Join-Path $pipelineRoot 'entrypoints\MediaPipeline.ps1'
$rerunCsvScript = Join-Path $pipelineRoot 'entrypoints\Invoke-RerunCsv.ps1'

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
    $missingMessage = "End-to-end smoke checks require: {0}" -f ($missingTools -join ', ')
    if ($AllowMissingTools) {
        Write-Host "SKIP: $missingMessage"
        return
    }
    throw $missingMessage
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
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

function Get-ProbeStreamCodecs {
    param([Parameter(Mandatory)] [string] $Path, [Parameter(Mandatory)] [string] $Selector)

    $jsonText = Invoke-SmokeCommand -FilePath $ffprobePath -Label "ffprobe $Selector $Path" -ArgumentList @(
        '-v', 'error',
        '-select_streams', $Selector,
        '-show_entries', 'stream=codec_name',
        '-of', 'json',
        '--',
        $Path
    )
    $probe = ($jsonText -join [Environment]::NewLine) | ConvertFrom-Json -ErrorAction Stop
    return @($probe.streams | ForEach-Object { [string]$_.codec_name })
}

function New-SmokeVideo {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [string] $AudioCodec = 'aac',
        [double] $DurationSeconds = 1.5,
        [int] $Frequency = 880
    )

    $args = @(
        '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'lavfi', '-i', "testsrc=size=64x64:rate=5:duration=$DurationSeconds",
        '-f', 'lavfi', '-i', "sine=frequency=${Frequency}:sample_rate=44100:duration=$DurationSeconds",
        '-shortest',
        '-c:v', 'mpeg4',
        '-q:v', '5',
        '-c:a', $AudioCodec,
        $Path
    )
    Invoke-SmokeCommand -FilePath $ffmpegPath -ArgumentList $args -Label "generate $Path" | Out-Null
    Assert-True ((Test-Path -LiteralPath $Path -PathType Leaf) -and ((Get-Item -LiteralPath $Path).Length -gt 0)) "failed to generate smoke media: $Path"
}

. (Join-Path $projectRoot 'ops\pipeline\engine\config\config_schema.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\shared\media_constants.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\shared\failure_codes.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\decide\encoder_descriptors.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\decide\encode_policy.ps1')

$workRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-e2e-smoke-" + [guid]::NewGuid().ToString('N'))
$sourceMovies = Join-Path $workRoot 'SourceMovies'
$sourceTv = Join-Path $workRoot 'SourceTV'
$outsource = Join-Path $workRoot 'Outsource'
$localBase = Join-Path $workRoot 'LocalBase'
$configPath = Join-Path $workRoot 'smoke_config.psd1'
$queuePath = Join-Path $workRoot 'queue_snapshot.json'
$previousMutexSuffix = $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX
$smokeSucceeded = $false

try {
    $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = [guid]::NewGuid().ToString('N')
    New-Item -ItemType Directory -Path $sourceMovies, $sourceTv, $outsource, $localBase -Force | Out-Null

    $movieSource = Join-Path $sourceMovies 'Smoke.Movie.2026.mp4'
    $audioSource = Join-Path $sourceMovies 'Audio.Transcode.2026.mkv'
    $tvDir = Join-Path $sourceTv 'Smoke Show'
    New-Item -ItemType Directory -Path $tvDir -Force | Out-Null
    $tvSource = Join-Path $tvDir 'Smoke.Show.S01E02.mp4'

    New-SmokeVideo -Path $movieSource -AudioCodec 'aac' -DurationSeconds 1.5 -Frequency 880
    New-SmokeVideo -Path $audioSource -AudioCodec 'pcm_s16le' -DurationSeconds 1.7 -Frequency 660
    New-SmokeVideo -Path $tvSource -AudioCodec 'aac' -DurationSeconds 2.1 -Frequency 990

    $config = [hashtable](Get-MediaPipelineConfigDefaultValues)
    $config['SourceMovies'] = $sourceMovies
    $config['SourceTV'] = $sourceTv
    $config['Outsource'] = $outsource
    $config['LocalBase'] = $localBase
    foreach ($profile in @($config['LibraryProfiles'])) {
        if (-not ($profile -is [System.Collections.IDictionary])) { continue }
        $designation = [string]$profile['designation']
        $id = [string]$profile['id']
        if ($designation -eq 'movie' -or $id -eq 'movies') {
            $profile['source_path'] = $sourceMovies
            $profile['output_path'] = $outsource
        } elseif ($designation -eq 'tv' -or $id -eq 'tv') {
            $profile['source_path'] = $sourceTv
            $profile['output_path'] = $outsource
        }
    }
    $config['MovieRoute1080pTargetSizeGB'] = 999
    $config['MovieRoute1440pTargetSizeGB'] = 999
    $config['MovieRoute4KTargetSizeGB'] = 999
    $config['TVRoute1080pTargetSizeGB'] = 999
    $config['TVRoute1440pTargetSizeGB'] = 999
    $config['TVRoute4KTargetSizeGB'] = 999
    $config['MinFreeSpaceGB'] = 1
    $config['OutsourceMinFreeSpaceGB'] = 1
    $config['DeferredPublish'] = $true
    $config['RemuxSafeVideoCodecs'] = @('mpeg4','h264','hevc','avc1')
    $config['CompatibleAudioCodecs'] = @('aac','ac3','eac3')
    $config['OutputContainer'] = 'mkv'
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
    $config['AggressiveEpisodeParsing'] = $true
    $config['RobocopyFlags'] = @('/R:1','/W:1','/NP','/NDL','/NFL')
    $config['RobocopyTimeoutSeconds'] = 60
    $config['FFmpegEncodeTimeoutSeconds'] = 300
    $config['FFmpegRemuxTimeoutSeconds'] = 300
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

    Invoke-SmokeCommand -FilePath $bundledPwshPath -Label 'pipeline queue plan smoke' -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', $mediaPipelineScript,
        '-ConfigPath', $configPath,
        '-EmitQueuePlan',
        '-QueuePlanOutPath', $queuePath
    ) | Out-Null
    $queuePlan = Get-Content -LiteralPath $queuePath -Raw | ConvertFrom-Json -ErrorAction Stop
    Assert-True ([int]$queuePlan.runnable_count -ge 3) 'queue dry-run did not include all smoke sources'
    $tvQueueRows = @($queuePlan.rows | Where-Object { [string]$_.source_path -match 'S01E02' })
    Assert-True ($tvQueueRows.Count -eq 1) "TV episode row missing from queue snapshot: $($queuePlan.rows | ConvertTo-Json -Depth 5)"
    Assert-True ([int]$tvQueueRows[0].season_number -eq 1 -and [int]$tvQueueRows[0].episode_number -eq 2) "TV episode planning did not parse S01E02 in queue snapshot: $($tvQueueRows[0] | ConvertTo-Json -Depth 5)"

    Invoke-SmokeCommand -FilePath $bundledPwshPath -Label 'pipeline deferred-publish processing smoke' -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', $mediaPipelineScript,
        '-ConfigPath', $configPath,
        '-Once'
    ) | Out-Null

    $runMonitorRoot = Join-Path $localBase 'State\RunMonitor'
    $unexpectedRunMonitors = @(
        Get-ChildItem -LiteralPath $runMonitorRoot -Filter '*.json' -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ne 'latest.json' }
    )
    Assert-True ($unexpectedRunMonitors.Count -eq 0) 'Standalone -Once must not invent a Backend Queue Run Monitor without an accepted fingerprint and adopted seed.'

    $pendingRoot = Join-Path $localBase 'State\PendingServerPush'
    $pendingManifests = @(Get-ChildItem -LiteralPath $pendingRoot -Filter '*.manifest.json' -File -ErrorAction SilentlyContinue)
    Assert-True ($pendingManifests.Count -ge 3) 'deferred publish did not park all smoke outputs'

    Invoke-SmokeCommand -FilePath $bundledPwshPath -Label 'pipeline deferred-publish drain smoke' -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', $mediaPipelineScript,
        '-ConfigPath', $configPath,
        '-DrainPendingPushes'
    ) | Out-Null

    $remainingPending = @(Get-ChildItem -LiteralPath $pendingRoot -Filter '*.manifest.json' -File -ErrorAction SilentlyContinue)
    Assert-True ($remainingPending.Count -eq 0) 'deferred publish drain left pending manifests behind'

    $outputs = @(Get-ChildItem -LiteralPath $outsource -Recurse -Filter '*.mkv' -File)
    Assert-True ($outputs.Count -ge 3) 'deferred publish drain did not publish all smoke outputs'
    Assert-True (@($outputs | Where-Object { $_.FullName -match 'Season 01' -and $_.Name -match 'S01E02' }).Count -eq 1) 'TV episode output path did not include expected season/episode naming'

    $audioOutput = @($outputs | Where-Object { $_.Name -match 'Audio|Transcode' } | Select-Object -First 1)
    Assert-True ($audioOutput.Count -eq 1) 'audio transcode smoke output was not found'
    $audioCodecs = Get-ProbeStreamCodecs -Path $audioOutput[0].FullName -Selector 'a'
    Assert-True ($audioCodecs -contains 'eac3') "PCM audio was not standardized to EAC3; codecs: $($audioCodecs -join ',')"

    $movieOutput = @($outputs | Where-Object { $_.Name -match 'Smoke Movie|Smoke.Movie' } | Select-Object -First 1)
    Assert-True ($movieOutput.Count -eq 1) 'movie remux smoke output was not found'
    $movieVideoCodecs = Get-ProbeStreamCodecs -Path $movieOutput[0].FullName -Selector 'v'
    Assert-True ($movieVideoCodecs -contains 'mpeg4') "movie remux smoke did not preserve the mpeg4 video stream; codecs: $($movieVideoCodecs -join ',')"

    $csvPath = Join-Path $workRoot 'rerun.csv'
    [System.IO.File]::WriteAllText($csvPath, "enabled,source_path,media_kind`r`ntrue,""$movieSource"",movie`r`n", [System.Text.UTF8Encoding]::new($false))
    Invoke-SmokeCommand -FilePath $bundledPwshPath -Label 'CSV rerun dry-run smoke' -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', $rerunCsvScript,
        '-CsvPath', $csvPath,
        '-ConfigPath', $configPath,
        '-DryRun',
        '-ConfirmReplaceFinal'
    ) | Out-Null
    $rerunManifest = @(Get-ChildItem -LiteralPath (Join-Path $localBase 'RerunManifests') -Filter '*.json' -File | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1)
    Assert-True ($rerunManifest.Count -eq 1) 'CSV rerun dry-run did not write a manifest'
    $rerunModel = Get-Content -LiteralPath $rerunManifest[0].FullName -Raw | ConvertFrom-Json -ErrorAction Stop
    Assert-True ([string]$rerunModel.status -eq 'dry_run_complete') 'CSV rerun dry-run manifest did not finish as dry_run_complete'
    Assert-True ([string]$rerunModel.rows[0].queue_item.queue_source -eq 'csv_rerun') 'CSV rerun dry-run did not preserve csv_rerun queue authority'

    $shouldFallback = Test-ShouldRetryEncodeWithCpuFallback -Success:$false -StopRequested:$false -ErrorText 'No NVENC capable devices found'
    Assert-True $shouldFallback 'GPU fallback policy did not recognize representative NVENC failure text'
    $fallbackOutput = Join-Path $workRoot 'cpu-fallback-smoke.mkv'
    $fallbackPlan = New-EncodeAttemptPlan `
        -UseCpuFallback:$true `
        -InputPath $movieSource `
        -GlobalTitle 'Smoke CPU fallback' `
        -AudioArgs @('-map','0:a?','-c:a','aac') `
        -SubtitleMapArgs @() `
        -OutputPath $fallbackOutput `
        -VideoCodec 'hevc_nvenc' `
        -VideoPreset 'p7' `
        -VideoQuality 24 `
        -ExtraVideoFlags @() `
        -FallbackCpuQuality 35
    Invoke-SmokeCommand -FilePath $ffmpegPath -ArgumentList @($fallbackPlan.ArgumentList) -Label 'CPU fallback encode smoke' | Out-Null
    Assert-True ((Test-Path -LiteralPath $fallbackOutput -PathType Leaf) -and ((Get-Item -LiteralPath $fallbackOutput).Length -gt 0)) 'CPU fallback encode smoke did not produce output'
    Assert-True ((Get-ProbeStreamCodecs -Path $fallbackOutput -Selector 'v') -contains 'hevc') 'CPU fallback encode smoke did not produce HEVC video'

    Write-Host 'End-to-end smoke checks passed.'
    $smokeSucceeded = $true
} finally {
    $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = $previousMutexSuffix
    if ($smokeSucceeded -or -not $env:MEDIA_PIPELINE_KEEP_FAILED_SMOKE) {
        Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue
    } else {
        Write-Warning "Keeping failed smoke workspace: $workRoot"
    }
}
