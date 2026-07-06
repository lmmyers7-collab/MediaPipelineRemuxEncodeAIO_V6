[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Rerun auto-destination checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
$realRerunScript = Join-Path $repoRoot 'ops\pipeline\entrypoints\Invoke-RerunCsv.ps1'
$realEngineRoot = Join-Path $repoRoot 'ops\pipeline\engine'

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string]$Message)
    if ($Actual -ne $Expected) { throw "$Message Expected=[$Expected] Actual=[$Actual]" }
}

function ConvertTo-NormalizedPath {
    param([string]$Path)
    return [System.IO.Path]::GetFullPath($Path).TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)).ToLowerInvariant()
}

function Write-MockNestedPipeline {
    param([Parameter(Mandatory)] [string]$Path)

    @'
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$ConfigPath,
    [switch]$Once,
    [int]$SleepSeconds = 1
)

$ErrorActionPreference = 'Stop'
$config = Import-PowerShellDataFile -LiteralPath $ConfigPath
if ([bool]$config['DeferredPublish']) {
    throw 'Nested rerun pipeline received DeferredPublish=true; rerun wrapper must force DeferredPublish=false.'
}
$outRoot = [string]$config['Outsource']
foreach ($sourceRootKey in @('SourceMovies','SourceTV')) {
    $sourceRoot = [string]$config[$sourceRootKey]
    if ([string]::IsNullOrWhiteSpace($sourceRoot) -or -not (Test-Path -LiteralPath $sourceRoot -PathType Container)) { continue }
    foreach ($file in @(Get-ChildItem -LiteralPath $sourceRoot -Recurse -File)) {
        $relative = [System.IO.Path]::GetRelativePath([System.IO.Path]::GetFullPath($sourceRoot), $file.FullName)
        $output = Join-Path $outRoot $relative
        $outputDir = Split-Path -Parent $output
        if (-not (Test-Path -LiteralPath $outputDir)) { New-Item -ItemType Directory -Path $outputDir -Force | Out-Null }
        Copy-Item -LiteralPath $file.FullName -Destination $output -Force
        $size = [long](Get-Item -LiteralPath $output -Force).Length
        $requiresReview = $file.Name -like '*Problem*'
        $srtPath = Join-Path $outputDir (([System.IO.Path]::GetFileNameWithoutExtension($output)) + '.eng.srt')
        Set-Content -LiteralPath $srtPath -Value "1`n00:00:00,000 --> 00:00:01,000`nHello" -Encoding UTF8
        $sidecar = [ordered]@{
            schema_version = 'pipeline_sidecar.v1'
            output_path = $output
            output_file = Split-Path -Leaf $output
            output_size = $size
            publish_state = 'published'
            publish_mode = 'immediate'
            sidecar_files = @()
            tx3g_srt_tracks = @(
                @{
                    path = $srtPath
                    file_name = Split-Path -Leaf $srtPath
                    status = 'written'
                    language = 'eng'
                    cue_count = 1
                }
            )
            tx3g_srt_failures = @()
            bdpgs_srt_failures = @()
            vobsub_srt_failures = @()
            tx3g_embedded_srt_tracks = @()
            bdpgs_embedded_srt_tracks = @()
            vobsub_embedded_srt_tracks = @()
            converted_srt_sidecar_candidates = @(@{ selected = $true; srt_path = $srtPath })
            subtitle_output_reduction = @()
            subtitle_decisions = @()
            tx3g_external_srt_sidecars_enabled = $true
            quality_verification = @{
                attempted = $true
                outcome = 'pass'
                block_publish = $false
            }
        }
        if ($requiresReview) {
            $sidecar['requires_review'] = $true
            $sidecar['warnings'] = @(@{ code = 'remaining_audit_issue'; message = 'mock remaining issue' })
        }
        $sidecarPath = Join-Path $outputDir (([System.IO.Path]::GetFileNameWithoutExtension($output)) + '.pipeline.json')
        $sidecar | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $sidecarPath -Encoding UTF8
    }
}
exit 0
'@ | Set-Content -LiteralPath $Path -Encoding UTF8
}

Assert-True (Test-Path -LiteralPath $realRerunScript -PathType Leaf) "Rerun script missing: $realRerunScript"
Assert-True (Test-Path -LiteralPath $realEngineRoot -PathType Container) "Engine root missing: $realEngineRoot"

$pwshHost = (Get-Process -Id $PID).Path
if (-not $pwshHost) { $pwshHost = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source }
if (-not $pwshHost) { $pwshHost = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
Assert-True (-not [string]::IsNullOrWhiteSpace($pwshHost)) 'PowerShell host path is required for rerun auto-destination checks.'

$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-rerun-auto-destination-' + [guid]::NewGuid().ToString('N'))
try {
    $mockPipelineRoot = Join-Path $root 'Pipeline'
    $mockEntrypointsRoot = Join-Path $mockPipelineRoot 'entrypoints'
    New-Item -ItemType Directory -Path $mockEntrypointsRoot -Force | Out-Null
    Copy-Item -LiteralPath $realRerunScript -Destination (Join-Path $mockEntrypointsRoot 'Invoke-RerunCsv.ps1') -Force
    Write-MockNestedPipeline -Path (Join-Path $mockEntrypointsRoot 'MediaPipeline.ps1')

    $mockEngineRoot = Join-Path $mockPipelineRoot 'engine'
    try {
        New-Item -ItemType Junction -Path $mockEngineRoot -Target $realEngineRoot -Force | Out-Null
    } catch {
        Copy-Item -LiteralPath $realEngineRoot -Destination $mockEngineRoot -Recurse -Force
    }

    $sourceRoot = Join-Path $root 'Sources'
    $completedFinalRoot = Join-Path $root 'CompletedTargets'
    $finalRoot = $completedFinalRoot
    $localBase = Join-Path $root 'Local'
    New-Item -ItemType Directory -Path $sourceRoot -Force | Out-Null

    $cleanSource = Join-Path $sourceRoot 'Clean Movie.mkv'
    $problemSource = Join-Path $sourceRoot 'Problem Movie.mkv'
    Set-Content -LiteralPath $cleanSource -Value 'clean rerun output media' -Encoding ASCII
    Set-Content -LiteralPath $problemSource -Value 'problem rerun output media' -Encoding ASCII

    $cleanFinal = Join-Path $completedFinalRoot 'Clean Library\Clean Movie.mkv'
    $problemFinal = Join-Path $completedFinalRoot 'Problem Library\Problem Movie.mkv'
    New-Item -ItemType Directory -Path (Split-Path -Parent $cleanFinal) -Force | Out-Null
    New-Item -ItemType Directory -Path (Split-Path -Parent $problemFinal) -Force | Out-Null
    Set-Content -LiteralPath $cleanFinal -Value 'old clean final' -Encoding ASCII
    Set-Content -LiteralPath $problemFinal -Value 'old problem final' -Encoding ASCII

    $existingPendingRoot = Join-Path $localBase 'State\PendingServerPush'
    New-Item -ItemType Directory -Path $existingPendingRoot -Force | Out-Null
    $existingPendingPayload = Join-Path $existingPendingRoot 'Existing Problem.mkv'
    Set-Content -LiteralPath $existingPendingPayload -Value 'existing pending output media' -Encoding ASCII
    [ordered]@{
        schema_version = 'pending_push_manifest.v1'
        manifest_state = 'parked'
        route = 'csv_rerun'
        local_file = $existingPendingPayload
        server_out = $problemFinal
        source_path = $problemSource
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $existingPendingRoot 'Existing Problem.manifest.json') -Encoding UTF8

    $config = Join-Path $root 'config.psd1'
    $escapedLocal = $localBase.Replace("'", "''")
    $escapedFinal = $finalRoot.Replace("'", "''")
@"
@{
    LocalBase = '$escapedLocal'
    Outsource = '$escapedFinal'
    OutputContainer = 'mkv'
    CreateTVSubfolder = `$true
    AggressiveEpisodeParsing = `$true
    ValidExtensions = @('.mkv')
    PriorityMarkers = @('!')
    DeferredPublish = `$true
}
"@ | Set-Content -LiteralPath $config -Encoding UTF8

    $csv = Join-Path $root 'rerun.csv'
@"
enabled,source_path,media_kind,stage_mode,post_success_original,return_mode,plex_planned_path
true,"$cleanSource",Movie,copy,keep,park,"$cleanFinal"
true,"$problemSource",Movie,copy,keep,park,"$problemFinal"
"@ | Set-Content -LiteralPath $csv -Encoding UTF8

    $mockRerunScript = Join-Path $mockEntrypointsRoot 'Invoke-RerunCsv.ps1'
    $argsList = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', $mockRerunScript,
        '-CsvPath', $csv,
        '-ConfigPath', $config,
        '-DefaultReturnMode', 'replace_original',
        '-DestinationMode', 'auto_replace_clean_else_pending_review',
        '-CollisionPolicy', 'replace_final',
        '-ConfirmReplaceFinal'
    )
    $output = & $pwshHost @argsList *>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "Auto destination rerun failed with exit $LASTEXITCODE. Output: $output"
    }

    Assert-True (Test-Path -LiteralPath $cleanSource -PathType Leaf) 'Clean source media was moved or removed.'
    Assert-True (Test-Path -LiteralPath $problemSource -PathType Leaf) 'Problem source media was moved or removed.'
    Assert-Equal (Get-Content -LiteralPath $cleanFinal -Raw).Trim() 'clean rerun output media' 'Clean final output was not replaced by verified rerun output.'
    Assert-Equal (Get-Content -LiteralPath $problemFinal -Raw).Trim() 'old problem final' 'Problem final output was replaced instead of routed to Pending Publish review.'

    $manifestPath = @(Get-ChildItem -LiteralPath (Join-Path $localBase 'RerunManifests') -Filter '*.json' -File | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1).FullName
    Assert-True (-not [string]::IsNullOrWhiteSpace($manifestPath)) 'Rerun manifest was not written.'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $cleanRow = @($manifest.rows | Where-Object { [string]$_.source_path -eq $cleanSource })[0]
    $problemRow = @($manifest.rows | Where-Object { [string]$_.source_path -eq $problemSource })[0]
    Assert-True ($null -ne $cleanRow) 'Clean row missing from rerun manifest.'
    Assert-True ($null -ne $problemRow) 'Problem row missing from rerun manifest.'
    Assert-Equal ([string]$cleanRow.status) 'published_replace_final' 'Clean row did not publish through replacement policy.'
    Assert-Equal ([string]$cleanRow.auto_destination_decision) 'published_replace_final' 'Clean row missing auto replacement decision evidence.'
    Assert-Equal (ConvertTo-NormalizedPath ([string]$cleanRow.final_output_path)) (ConvertTo-NormalizedPath $cleanFinal) 'Clean row did not use the CSV completed destination path.'
    Assert-Equal ([string]$cleanRow.final_output_source) 'csv_completed_output' 'Clean row did not record CSV completed destination evidence.'
    Assert-Equal ([string]$cleanRow.final_output_source_field) 'plex_planned_path' 'Clean row did not record the CSV completed destination field.'
    Assert-Equal ([string]$cleanRow.completed_manifest_append) 'appended' 'Clean row did not append replacement output to completed jobs manifest.'
    $tempConfigs = @(Get-ChildItem -LiteralPath (Join-Path $localBase 'RerunManifests') -Filter '*.config.psd1' -File)
    Assert-True ($tempConfigs.Count -ge 1) 'Rerun temp config fixture did not write chunk config evidence.'
    foreach ($tempConfigPath in $tempConfigs) {
        $tempConfig = Import-PowerShellDataFile -LiteralPath $tempConfigPath.FullName
        Assert-Equal ([bool]$tempConfig['DeferredPublish']) $false "Temp rerun config did not force DeferredPublish false: $($tempConfigPath.FullName)"
    }
    Assert-Equal ([bool]$manifest.nested_pipeline_deferred_publish) $false 'Rerun manifest did not record nested DeferredPublish=false.'
    Assert-Equal ([bool]$manifest.nested_pipeline_deferred_publish_forced) $true 'Rerun manifest did not record forced nested DeferredPublish evidence.'
    $cleanSrt = [System.IO.Path]::ChangeExtension($cleanFinal, '.eng.srt')
    Assert-True (Test-Path -LiteralPath $cleanSrt -PathType Leaf) 'Clean replacement SRT sidecar was not published beside the final output.'
    Assert-Equal ([string]$problemRow.status) 'pending_publish' 'Problem row did not route to Pending Publish.'
    Assert-Equal ([string]$problemRow.auto_destination_decision) 'pending_publish_review' 'Problem row missing auto Pending Publish decision evidence.'
    Assert-True ([int]$problemRow.auto_destination_issue_count -gt 0) 'Problem row did not preserve remaining issue evidence.'

    $cleanBackup = @(Get-ChildItem -LiteralPath (Join-Path $localBase 'State\Rerun\FinalReplaced') -Recurse -File -Filter 'Clean Movie.mkv')
    Assert-True ($cleanBackup.Count -ge 1) 'Existing clean final output was not held before replacement.'
    $pendingManifestPath = [string]$problemRow.pending_publish_manifest_path
    Assert-True (Test-Path -LiteralPath $pendingManifestPath -PathType Leaf) 'Problem row Pending Publish manifest was not written.'
    $pendingManifest = Get-Content -LiteralPath $pendingManifestPath -Raw | ConvertFrom-Json
    Assert-Equal ([string]$pendingManifest.route_reason_code) 'rerun_csv_auto_pending_review' 'Pending manifest does not record auto-review route reason.'
    Assert-Equal ([string]$pendingManifest.rerun_auto_destination_policy) 'auto_replace_clean_else_pending_review' 'Pending manifest missing auto destination policy evidence.'
    Assert-Equal ([string]$pendingManifest.rerun_auto_destination_decision) 'pending_publish_review' 'Pending manifest missing auto destination decision evidence.'
    Assert-True (@($pendingManifest.rerun_auto_review_issues).Count -gt 0) 'Pending manifest missing auto review issues.'
    Assert-True (Test-Path -LiteralPath ([string]$pendingManifest.local_file) -PathType Leaf) 'Pending payload file was not parked.'
    $pendingServerOut = [string]$pendingManifest.server_out
    Assert-True ((ConvertTo-NormalizedPath $pendingServerOut) -ne (ConvertTo-NormalizedPath $problemFinal)) 'Pending manifest reused an already-queued server_out.'
    Assert-Equal (ConvertTo-NormalizedPath (Split-Path -Parent $pendingServerOut)) (ConvertTo-NormalizedPath (Split-Path -Parent $problemFinal)) 'Pending manifest server_out moved outside the backend-planned final folder.'
    Assert-True ((Split-Path -Leaf $pendingServerOut) -like 'Problem Movie.rerun_*.mkv') 'Pending manifest server_out was not suffixed for the pending collision.'
    $pendingSidecars = @($pendingManifest.sidecar_files)
    Assert-True ($pendingSidecars.Count -ge 1) 'Pending manifest did not carry converted SRT sidecar entries.'
    foreach ($sidecar in $pendingSidecars) {
        Assert-True (Test-Path -LiteralPath ([string]$sidecar.local_file) -PathType Leaf) 'Pending sidecar payload was not copied.'
        Assert-Equal (ConvertTo-NormalizedPath (Split-Path -Parent ([string]$sidecar.server_out))) (ConvertTo-NormalizedPath (Split-Path -Parent $pendingServerOut)) 'Pending sidecar server_out moved outside the final output folder.'
        Assert-True ((ConvertTo-NormalizedPath ([string]$sidecar.server_out)).StartsWith((ConvertTo-NormalizedPath $completedFinalRoot))) 'Pending sidecar server_out moved outside the configured output root.'
    }
    $pendingServerOuts = @(
        Get-ChildItem -LiteralPath $existingPendingRoot -Filter '*.manifest.json' -File |
            ForEach-Object { (Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json).server_out } |
            Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } |
            ForEach-Object { ConvertTo-NormalizedPath ([string]$_) }
    )
    Assert-Equal ([int]$pendingServerOuts.Count) ([int]@($pendingServerOuts | Sort-Object -Unique).Count) 'Pending manifests reused a server_out destination.'
    $completedManifest = Join-Path $localBase 'State\Completed\completed_jobs.jsonl'
    Assert-True (Test-Path -LiteralPath $completedManifest -PathType Leaf) 'Completed jobs manifest was not written for the clean replacement.'
    $completedRows = @(Get-Content -LiteralPath $completedManifest | ForEach-Object { $_ | ConvertFrom-Json })
    $cleanCompleted = @($completedRows | Where-Object { (ConvertTo-NormalizedPath ([string]$_.output_path)) -eq (ConvertTo-NormalizedPath $cleanFinal) })
    Assert-Equal ([int]$cleanCompleted.Count) 1 'Completed jobs manifest should contain exactly one clean replacement entry.'
    Assert-Equal ([string]$cleanCompleted[0].rerun_batch_id) ([string]$manifest.batch_id) 'Completed jobs manifest missing rerun batch evidence.'
    Assert-Equal ([string]$cleanCompleted[0].rerun_destination_policy) 'auto_replace_clean_else_pending_review' 'Completed jobs manifest missing rerun destination policy.'
    Assert-Equal ([bool]$cleanCompleted[0].rerun_final_replacement) $true 'Completed jobs manifest missing final replacement evidence.'
    Assert-Equal ([string]$cleanCompleted[0].completed_manifest_source) 'csv_rerun_replace_final' 'Completed jobs manifest missing rerun append source.'

    $blockedLocalBase = Join-Path $root 'BlockedLocal'
    $blockedSource = Join-Path $sourceRoot 'Blocked Movie.mkv'
    $blockedFinal = Join-Path $root 'OutsideBlocked\Blocked Movie.mkv'
    Set-Content -LiteralPath $blockedSource -Value 'blocked media' -Encoding ASCII
    $blockedConfig = Join-Path $root 'blocked-config.psd1'
    $escapedBlockedLocal = $blockedLocalBase.Replace("'", "''")
    $escapedAllowedFinal = $completedFinalRoot.Replace("'", "''")
@"
@{
    LocalBase = '$escapedBlockedLocal'
    Outsource = '$escapedAllowedFinal'
    OutputContainer = 'mkv'
    CreateTVSubfolder = `$true
    AggressiveEpisodeParsing = `$true
    ValidExtensions = @('.mkv')
    PriorityMarkers = @('!')
    DeferredPublish = `$true
}
"@ | Set-Content -LiteralPath $blockedConfig -Encoding UTF8
    $blockedCsv = Join-Path $root 'rerun-outside-root.csv'
@"
enabled,source_path,media_kind,stage_mode,post_success_original,return_mode,server_out
true,"$blockedSource",Movie,copy,keep,park,"$blockedFinal"
"@ | Set-Content -LiteralPath $blockedCsv -Encoding UTF8
    $blockedArgs = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', $mockRerunScript,
        '-CsvPath', $blockedCsv,
        '-ConfigPath', $blockedConfig,
        '-DefaultReturnMode', 'pending_publish',
        '-DestinationMode', 'pending_publish',
        '-CollisionPolicy', 'suffix'
    )
    $blockedOutput = & $pwshHost @blockedArgs *>&1 | Out-String
    Assert-True ($LASTEXITCODE -ne 0) 'Outside-root server_out rerun should fail with no executable rows.'
    Assert-True ($blockedOutput -match 'final output destination from server_out resolves outside configured output root') 'Outside-root server_out run did not report root validation failure.'
    Assert-True (Test-Path -LiteralPath $blockedSource -PathType Leaf) 'Outside-root blocked fixture moved or removed source media.'
    Assert-True (-not (Test-Path -LiteralPath $blockedFinal -PathType Leaf)) 'Outside-root blocked fixture wrote final media.'
    $blockedPendingRoot = Join-Path $blockedLocalBase 'State\PendingServerPush'
    Assert-True (-not (Test-Path -LiteralPath $blockedPendingRoot -PathType Container) -or @(Get-ChildItem -LiteralPath $blockedPendingRoot -Filter '*.manifest.json' -File -ErrorAction SilentlyContinue).Count -eq 0) 'Outside-root blocked fixture created pending manifests.'
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'Rerun auto-destination checks passed.'
