[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Rerun nested config checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
$rerunScript = Join-Path $repoRoot 'ops\pipeline\entrypoints\Invoke-RerunCsv.ps1'
$bundledPwsh = Join-Path $repoRoot 'ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe'
$ffmpegPath = Join-Path $repoRoot 'ops\pipeline\tools\ffmpeg\bin\ffmpeg.exe'

function Assert-True {
    param(
        [bool] $Condition,
        [string] $Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-False {
    param(
        [bool] $Condition,
        [string] $Message
    )
    if ($Condition) { throw $Message }
}

function Assert-Equal {
    param(
        [string] $Actual,
        [string] $Expected,
        [string] $Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function ConvertTo-ComparablePath {
    param([string] $Path)
    return [System.IO.Path]::GetFullPath($Path).TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))
}

function Test-NestedOrSamePath {
    param(
        [string] $Left,
        [string] $Right
    )
    $leftPath = ConvertTo-ComparablePath $Left
    $rightPath = ConvertTo-ComparablePath $Right
    return $leftPath.Equals($rightPath, [System.StringComparison]::OrdinalIgnoreCase) -or
        $leftPath.StartsWith($rightPath + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase) -or
        $rightPath.StartsWith($leftPath + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}

Assert-True (Test-Path -LiteralPath $rerunScript -PathType Leaf) "Rerun script missing: $rerunScript"
Assert-True (Test-Path -LiteralPath $bundledPwsh -PathType Leaf) "Bundled PowerShell missing: $bundledPwsh"
Assert-True (Test-Path -LiteralPath $ffmpegPath -PathType Leaf) "Bundled ffmpeg missing: $ffmpegPath"

$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-rerun-nested-config-' + [guid]::NewGuid().ToString('N'))
try {
    $sourceMovies = Join-Path $root 'SourceMovies'
    $sourceTv = Join-Path $root 'SourceTV'
    $localBase = Join-Path $root 'Local'
    $outsource = Join-Path $root 'Out'
    New-Item -ItemType Directory -Path $sourceMovies, $sourceTv, $localBase, $outsource -Force | Out-Null

    $source = Join-Path $sourceMovies 'Tiny Rerun (2026).mkv'
    $ffmpegOutput = & $ffmpegPath -y -hide_banner -loglevel error -f lavfi -i 'testsrc=size=16x16:rate=1' -t 1 -c:v mpeg4 $source *>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to generate synthetic rerun media with ffmpeg. Output: $ffmpegOutput"
    }

    $config = Join-Path $root 'config.psd1'
    $escapedSourceMovies = $sourceMovies.Replace("'", "''")
    $escapedSourceTv = $sourceTv.Replace("'", "''")
    $escapedLocalBase = $localBase.Replace("'", "''")
    $escapedOutsource = $outsource.Replace("'", "''")
    @"
@{
    SourceMovies = '$escapedSourceMovies'
    SourceTV = '$escapedSourceTv'
    LocalBase = '$escapedLocalBase'
    Outsource = '$escapedOutsource'
    LibraryProfiles = @(
        @{
            id = 'movies'
            name = 'Movies'
            enabled = `$true
            designation = 'movie'
            source_path = '$escapedSourceMovies'
            output_path = '$escapedOutsource'
            promotion_enabled = `$true
            promotion_destination = '$escapedOutsource'
        },
        @{
            id = 'tv'
            name = 'TV'
            enabled = `$true
            designation = 'tv'
            source_path = '$escapedSourceTv'
            output_path = '$escapedOutsource'
            promotion_enabled = `$true
            promotion_destination = '$escapedOutsource'
        }
    )
    OutputContainer = 'mkv'
    VideoCodec = 'hevc_nvenc'
    EncoderBackend = 'nvenc'
    VideoPreset = 'p7'
    VideoQuality = 24
    CreateTVSubfolder = `$true
    AggressiveEpisodeParsing = `$true
    ReprocessAll = `$true
    SkipStabilityCheck = `$true
    ValidExtensions = @('.mkv')
    PriorityMarkers = @('!')
    CompatibleAudioCodecs = @('aac','ac3','eac3','mp3','opus','vorbis','truehd','mlp')
    AllowNoAudio = `$true
    SubKeepLanguages = @('eng','en','und','')
    SubSDHTitleKeywords = @('sdh','cc','closed caption','hearing impaired')
    SubSupplementalKeywords = @('sign','song','karaoke','chapter','opening','ending')
    DropAssAfterConversion = `$false
    RemuxSafeVideoCodecs = @('mpeg4','hevc','h265','h.265')
    FileStabilityWait = 0
    EnableIntegrityCheck = `$false
    RobocopyFlags = @('/J','/R:1','/W:1','/NP','/NDL','/NFL')
    DebugMode = `$true
    MinFreeSpaceGB = 0
    OutsourceMinFreeSpaceGB = 0
    'custom-map' = @{
        'path key' = 'value with spaces'
        'dotted.key' = 'value.with.dots'
    }
}
"@ | Set-Content -LiteralPath $config -Encoding UTF8

    $csv = Join-Path $root 'rerun.csv'
    @"
enabled,source_path,media_kind,stage_mode,post_success_original,return_mode
true,"$source",Movie,copy,keep,park
"@ | Set-Content -LiteralPath $csv -Encoding UTF8

    $operatorPendingRoot = Join-Path $localBase 'State\PendingServerPush'
    New-Item -ItemType Directory -Path $operatorPendingRoot -Force | Out-Null
    $operatorPendingPayload = Join-Path $operatorPendingRoot 'Already Queued.mkv'
    Set-Content -LiteralPath $operatorPendingPayload -Value 'queued' -Encoding UTF8
    $operatorPendingManifest = Join-Path $operatorPendingRoot 'Already Queued.mkv.manifest.json'
    @{
        schema_version = 'pending_push_manifest.v1'
        manifest_state = 'parked'
        local_file = $operatorPendingPayload
        server_out = (Join-Path $outsource 'Already Queued.mkv')
        source_path = (Join-Path $sourceMovies 'Already Queued Source.mkv')
        route = 'remux'
        output_size = (Get-Item -LiteralPath $operatorPendingPayload).Length
        sidecar_files = @()
        tx3g_srt_tracks = @()
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $operatorPendingManifest -Encoding UTF8

    $rerunArgs = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', $rerunScript,
        '-CsvPath', $csv,
        '-ConfigPath', $config,
        '-DefaultReturnMode', 'replace_original',
        '-DestinationMode', 'auto_replace_clean_else_pending_review',
        '-CollisionPolicy', 'replace_final',
        '-ConfirmReplaceFinal'
    )
    $previousMutexSuffix = $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX
    try {
        $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = 'rerun_nested_' + [guid]::NewGuid().ToString('N')
        $runOutput = & $bundledPwsh @rerunArgs *>&1 | ForEach-Object { [string]$_ }
    } finally {
        if ($null -eq $previousMutexSuffix) {
            Remove-Item Env:\MEDIA_PIPELINE_TEST_MUTEX_SUFFIX -ErrorAction SilentlyContinue
        } else {
            $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = $previousMutexSuffix
        }
    }
    $output = $runOutput -join [Environment]::NewLine

    Assert-False ($output -match 'LocalBase and (Outsource|SourceMovies|SourceTV) must not be nested inside each other') "CSV rerun still emits nested LocalBase validation errors. Output: $output"
    Assert-False ($output -match 'Another instance of MediaPipeline is already running') "CSV rerun nested pipeline collided with an external controller mutex. Output: $output"
    Assert-True ($output -match 'Nested pipeline LocalBase:') "CSV rerun did not log nested pipeline LocalBase evidence. Output: $output"
    Assert-True ($output -match 'CSV rerun workspace:') "CSV rerun did not log isolated rerun workspace evidence. Output: $output"
    Assert-True ($output -match 'CSV rerun library profiles rewritten to staged roots') "CSV rerun did not log library profile rewrite evidence. Output: $output"

    $manifestRoot = Join-Path $localBase 'RerunManifests'
    $manifestFiles = @(Get-ChildItem -LiteralPath $manifestRoot -Filter '*.json' -File -ErrorAction SilentlyContinue)
    $tempConfigFiles = @(Get-ChildItem -LiteralPath $manifestRoot -Filter '*.config.psd1' -File -ErrorAction SilentlyContinue)
    Assert-True ($manifestFiles.Count -eq 1) "Expected one rerun manifest under operator-visible LocalBase; found $($manifestFiles.Count). Output: $output"
    Assert-True ($tempConfigFiles.Count -eq 1) "Expected one rerun temp config under operator-visible LocalBase; found $($tempConfigFiles.Count). Output: $output"

    $manifest = Get-Content -LiteralPath $manifestFiles[0].FullName -Raw | ConvertFrom-Json -ErrorAction Stop
    $tempConfig = Import-PowerShellDataFile -LiteralPath $tempConfigFiles[0].FullName
    $workspaceRoot = Join-Path $root 'Local_RerunWorkspace'
    $nestedRuntimeRoot = Join-Path $workspaceRoot 'RuntimeState'
    $chunkLocalBase = Join-Path $nestedRuntimeRoot ("{0}.chunk_0001" -f [string]$manifest.batch_id)

    Assert-Equal (ConvertTo-ComparablePath ([string]$manifest.pipeline_local_base)) (ConvertTo-ComparablePath $localBase) 'Manifest pipeline_local_base should preserve the operator-visible LocalBase.'
    Assert-Equal (ConvertTo-ComparablePath ([string]$manifest.nested_pipeline_local_base)) (ConvertTo-ComparablePath $nestedRuntimeRoot) 'Manifest nested_pipeline_local_base should point at the isolated nested runtime root.'
    Assert-Equal ([string]$manifest.nested_pipeline_local_base_mode) 'per_chunk_children' 'Manifest should identify that nested pipeline LocalBase values are per-chunk children.'
    Assert-Equal (ConvertTo-ComparablePath ([string]$manifest.nested_pipeline_runtime_root)) (ConvertTo-ComparablePath $nestedRuntimeRoot) 'Manifest nested_pipeline_runtime_root should point at the isolated nested runtime root.'
    Assert-Equal (ConvertTo-ComparablePath ([string]$manifest.rerun_workspace_root)) (ConvertTo-ComparablePath $workspaceRoot) 'Manifest rerun_workspace_root should point at the isolated sibling workspace.'
    Assert-Equal (ConvertTo-ComparablePath ([string]$tempConfig['LocalBase'])) (ConvertTo-ComparablePath $chunkLocalBase) 'Nested pipeline temp config should use an isolated per-chunk rerun runtime state.'
    Assert-True ((ConvertTo-ComparablePath ([string]$tempConfig['SourceMovies'])).StartsWith((ConvertTo-ComparablePath $workspaceRoot) + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) 'Temp SourceMovies should live under the isolated rerun workspace.'
    Assert-True ((ConvertTo-ComparablePath ([string]$tempConfig['Outsource'])).StartsWith((ConvertTo-ComparablePath $workspaceRoot) + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) 'Temp Outsource should live under the isolated rerun workspace.'
    Assert-False (Test-NestedOrSamePath ([string]$tempConfig['LocalBase']) ([string]$tempConfig['SourceMovies'])) 'Temp LocalBase and SourceMovies should not be nested or identical.'
    Assert-False (Test-NestedOrSamePath ([string]$tempConfig['LocalBase']) ([string]$tempConfig['SourceTV'])) 'Temp LocalBase and SourceTV should not be nested or identical.'
    Assert-False (Test-NestedOrSamePath ([string]$tempConfig['LocalBase']) ([string]$tempConfig['Outsource'])) 'Temp LocalBase and Outsource should not be nested or identical.'
    Assert-Equal ([string]$tempConfig['custom-map']['path key']) 'value with spaces' 'Temp config should preserve quoted custom map keys with spaces.'
    Assert-Equal ([string]$tempConfig['custom-map']['dotted.key']) 'value.with.dots' 'Temp config should preserve quoted custom map keys with dots.'

    $profiles = @($tempConfig['LibraryProfiles'])
    $movieProfile = @($profiles | Where-Object { [string]$_['id'] -eq 'movies' } | Select-Object -First 1)
    $tvProfile = @($profiles | Where-Object { [string]$_['id'] -eq 'tv' } | Select-Object -First 1)
    $expectedStageBatchRoot = Join-Path (Join-Path $workspaceRoot 'RerunQueue') ([string]$manifest.batch_id)
    $expectedStageMovies = Join-Path $expectedStageBatchRoot 'Movies'
    $expectedStageTv = Join-Path $expectedStageBatchRoot 'TV'
    Assert-True (Test-Path -LiteralPath $expectedStageMovies -PathType Container) 'Live rerun must create the staged Movies root before launching the nested pipeline.'
    Assert-True (Test-Path -LiteralPath $expectedStageTv -PathType Container) 'Live movie-only rerun must still create the empty staged TV root required by nested autonomy health.'
    Assert-True ($movieProfile.Count -eq 1) 'Temp config should preserve the movies library profile.'
    Assert-True ($tvProfile.Count -eq 1) 'Temp config should preserve the tv library profile.'
    Assert-Equal (ConvertTo-ComparablePath ([string]$movieProfile[0]['source_path'])) (ConvertTo-ComparablePath $expectedStageMovies) 'Movies profile should point at staged Movies.'
    Assert-Equal (ConvertTo-ComparablePath ([string]$tvProfile[0]['source_path'])) (ConvertTo-ComparablePath $expectedStageTv) 'TV profile should point at staged TV.'
    Assert-Equal (ConvertTo-ComparablePath ([string]$movieProfile[0]['output_path'])) (ConvertTo-ComparablePath ([string]$tempConfig['Outsource'])) 'Movies profile output should point at parked rerun output.'
    Assert-Equal (ConvertTo-ComparablePath ([string]$tvProfile[0]['output_path'])) (ConvertTo-ComparablePath ([string]$tempConfig['Outsource'])) 'TV profile output should point at parked rerun output.'
    Assert-False ([bool]$movieProfile[0]['promotion_enabled']) 'Movies profile promotion should be disabled in rerun temp config.'
    Assert-False ([bool]$tvProfile[0]['promotion_enabled']) 'TV profile promotion should be disabled in rerun temp config.'

    $manifestRows = @($manifest.rows)
    Assert-True ($manifestRows.Count -ge 1) 'Manifest should include at least one rerun row.'
    Assert-Equal (ConvertTo-ComparablePath ([string]$manifestRows[0].nested_pipeline_local_base)) (ConvertTo-ComparablePath $chunkLocalBase) 'Manifest row should record the actual per-chunk nested LocalBase.'
    Assert-Equal (ConvertTo-ComparablePath ([string]$manifestRows[0].nested_pipeline_runtime_root)) (ConvertTo-ComparablePath $nestedRuntimeRoot) 'Manifest row should record the batch nested runtime root.'
    Assert-Equal ([string]$manifestRows[0].rerun_chunk_index) '1' 'Manifest row should record its rerun chunk index.'

    $queueSnapshot = Join-Path $chunkLocalBase 'State\Progress\queue_snapshot.json'
    Assert-True (Test-Path -LiteralPath $queueSnapshot -PathType Leaf) "Nested pipeline did not write the isolated runtime queue snapshot: $queueSnapshot. Output: $output"
    $queueModel = Get-Content -LiteralPath $queueSnapshot -Raw | ConvertFrom-Json -ErrorAction Stop
    Assert-True ([int]$queueModel.total_row_count -ge 1) "Nested pipeline queue snapshot did not include staged rerun rows. Output: $output"
    Assert-True (Test-Path -LiteralPath $operatorPendingManifest -PathType Leaf) 'Nested rerun should leave pre-existing operator pending manifests in place.'
    Assert-True (Test-Path -LiteralPath $operatorPendingPayload -PathType Leaf) 'Nested rerun should leave pre-existing operator pending payloads in place.'
    $operatorPendingSummary = Join-Path $localBase 'State\Progress\pending_drain_summary.json'
    Assert-False (Test-Path -LiteralPath $operatorPendingSummary -PathType Leaf) "Nested rerun should not write operator pending drain summary evidence: $operatorPendingSummary. Output: $output"
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'Rerun nested config checks passed.'
