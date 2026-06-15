[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Contract schema checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSCommandPath."
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -PathType Container)) {
    throw "Resolved repository root is missing ops\pipeline\engine: $repoRoot"
}
$schemasRoot = Join-Path $pipelineRoot 'config\schemas'

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param(
        $Actual,
        $Expected,
        [string]$Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Convert-RoundTripJson {
    param(
        [Parameter(Mandatory)] $Payload,
        [int] $Depth = 8
    )
    return ($Payload | ConvertTo-Json -Depth $Depth -Compress) | ConvertFrom-Json -ErrorAction Stop
}

$expectedSchemas = @(
    'media_pipeline_pipeline_event.schema.json',
    'media_pipeline_process_file_result.schema.json',
    'media_pipeline_queue_plan_snapshot.schema.json',
    'media_pipeline_pending_push_manifest.schema.json',
    'media_pipeline_completed_job.schema.json',
    'media_pipeline_progress.schema.json'
)

foreach ($schemaName in $expectedSchemas) {
    $schemaPath = Join-Path $schemasRoot $schemaName
    Assert-True (Test-Path -LiteralPath $schemaPath -PathType Leaf) "Missing schema: $schemaName"
    $schema = Get-Content -LiteralPath $schemaPath -Raw | ConvertFrom-Json -ErrorAction Stop
    Assert-Equal $schema.'$schema' 'https://json-schema.org/draft/2020-12/schema' "Schema draft mismatch for $schemaName."
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$schema.'$id')) "Schema id missing for $schemaName."
}

$event = Convert-RoundTripJson ([ordered]@{
    schema_version = 'pipeline_event.v1'
    event_id       = 'event-test'
    event_type     = 'job_completed'
    timestamp      = '2026-05-06T12:00:00Z'
    created_at     = '2026-05-06T12:00:00Z'
    run_id         = 'run-test'
    correlation_id = 'run-test'
    job_id         = 'job-test'
    stage          = 'completed'
    route          = 'remux'
    status         = 'succeeded'
    source_path    = 'C:\Media\Source\Movie.mkv'
    data           = [ordered]@{
        schema_version    = 'process_file_result.v1'
        success           = $true
        completion_status = 'processed'
        output_path       = 'C:\Media\Out\Movie.mkv'
    }
})
Assert-Equal $event.schema_version 'pipeline_event.v1' 'Pipeline event schema_version mismatch.'
Assert-Equal $event.data.schema_version 'process_file_result.v1' 'Nested process result schema_version mismatch.'

$processResult = Convert-RoundTripJson ([pscustomobject]@{
    SchemaVersion   = 'process_file_result.v1'
    Success         = $true
    Status          = 'processed'
    QueueTerminal   = $true
    Retryable       = $false
    Reason          = ''
    ErrorCode       = ''
    SourcePath      = 'C:\Media\Source\Movie.mkv'
    SourceName      = 'Movie.mkv'
    Route           = 'remux'
    OutputPath      = 'C:\Media\Out\Movie.mkv'
    OutputSizeBytes = 42
})
Assert-Equal $processResult.SchemaVersion 'process_file_result.v1' 'Process-file result schema_version mismatch.'
Assert-True ([bool]$processResult.Success) 'Process-file result Success did not round-trip as bool.'

$queueSnapshot = Convert-RoundTripJson ([pscustomobject]@{
    schema_version    = 'queue_plan_snapshot.v1'
    produced_at       = '2026-05-06T12:00:00Z'
    config_path       = 'C:\Config\MediaPipeline.psd1'
    local_base        = 'C:\Scratch'
    movie_count_total = 1
    tv_count_total    = 0
    priority_count    = 0
    runnable_count    = 1
    rows              = @(
        [ordered]@{
            global_order      = 0
            phase             = 'movie'
            media_kind        = 'movie'
            queue_index       = 1
            queue_total       = 1
            is_priority       = $false
            source_path       = 'C:\Media\Source\Movie.mkv'
            root_path         = 'C:\Media\Source'
            display_name      = 'Movie.mkv'
            size_gb           = 1.5
            route             = 'REMUX'
            route_reason_code = 'CONTAINER_ONLY'
            route_reason      = 'Container normalization only'
        }
    )
})
Assert-Equal $queueSnapshot.schema_version 'queue_plan_snapshot.v1' 'Queue snapshot schema_version mismatch.'
Assert-Equal @($queueSnapshot.rows).Count 1 'Queue snapshot rows did not round-trip as an array.'

$pendingManifest = Convert-RoundTripJson ([ordered]@{
    schema_version         = 'pending_push_manifest.v1'
    parked_at              = '2026-05-06T12:00:00Z'
    pipeline_version       = '4'
    publish_transaction_id = 'tx-test'
    manifest_state         = 'parked'
    local_file             = 'C:\Scratch\Pending\Movie.mkv'
    original_local_file    = 'C:\Scratch\Movie.mkv'
    parked_file            = 'C:\Scratch\Pending\Movie.mkv'
    server_out             = '\\server\Movies\Movie.mkv'
    route                  = 'remux'
    media_type             = 'movie'
    source_path            = 'C:\Media\Source\Movie.mkv'
    source_size            = 42
    source_mtime_utc       = '2026-05-06T11:59:00Z'
    output_size            = 42
    publish_mode           = 'deferred'
    sidecar_files          = @([ordered]@{ local_file = 'C:\Scratch\Pending\Movie.eng.srt'; server_out = '\\server\Movies\Movie.eng.srt' })
    tx3g_srt_tracks        = @([ordered]@{ language = 'eng' })
    tx3g_srt_failures      = @()
    bdpgs_srt_failures     = @()
    vobsub_srt_failures    = @([ordered]@{ reason = 'ocr unavailable' })
    tx3g_embedded_srt_tracks = @([ordered]@{ language = 'eng' })
    bdpgs_embedded_srt_tracks = @()
    vobsub_embedded_srt_tracks = @([ordered]@{ language = 'eng' })
    vobsub_srt_conversion_enabled = $true
    drop_vobsub_after_conversion = $false
})
Assert-Equal $pendingManifest.schema_version 'pending_push_manifest.v1' 'Pending manifest schema_version mismatch.'
Assert-Equal $pendingManifest.manifest_state 'parked' 'Pending manifest state mismatch.'
Assert-Equal $pendingManifest.media_type 'movie' 'Pending manifest media_type mismatch.'
Assert-Equal @($pendingManifest.vobsub_srt_failures).Count 1 'Pending manifest VobSub failure evidence did not round-trip.'
Assert-True ([bool]$pendingManifest.vobsub_srt_conversion_enabled) 'Pending manifest VobSub conversion flag did not round-trip.'

$completedJob = Convert-RoundTripJson ([ordered]@{
    schema_version   = 'pipeline_sidecar.v1'
    pipeline_version = '4'
    created_at       = '2026-05-06T12:00:00Z'
    encoded_at       = '2026-05-06T12:00:00Z'
    logged_at        = '2026-05-06T12:01:00Z'
    route            = 'encode'
    output_file      = 'Movie.mkv'
    output_path      = '\\server\Movies\Movie.mkv'
})
Assert-Equal $completedJob.schema_version 'pipeline_sidecar.v1' 'Completed manifest compatibility schema mismatch.'

. (Join-Path $repoRoot 'ops\pipeline\engine\publish\publish_result.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\publish_partial.ps1')
$publishResult = New-PipelinePublishResult -Ok:$true -DeleteLocalOutput:$true -PublishState 'published' -PublishMode 'immediate' -OutputPath 'C:\Out\Movie.mkv' -OutputSizeBytes 42
Assert-True ([bool]$publishResult.Ok) 'Publish result Ok did not round-trip as bool.'
Assert-True ([bool]$publishResult.DeleteLocalOutput) 'Publish result DeleteLocalOutput did not round-trip as bool.'
Assert-Equal $publishResult.PublishState 'published' 'Publish result state mismatch.'
Assert-Equal $publishResult.OutputSizeBytes 42 'Publish result output size mismatch.'
$partialPath = New-PublishPartialMediaPath -ServerOut 'C:\Out\Movie.mkv' -PublishTransactionId 'tx-test'
Assert-True ($partialPath -like '*Movie.mkv.mp-publish-partial.tx-test') 'Publish partial path format changed.'

. (Join-Path $repoRoot 'ops\pipeline\engine\config\config_keys.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\config\config_schema.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\policy\folder_policy.ps1')
if (-not (Get-Command Write-Log -ErrorAction SilentlyContinue)) {
    function Write-Log { param([string] $Message, [string] $Level = 'INFO') }
}
$zeroBitratePolicy = Convert-RoundTripJson ([ordered]@{
    schema_version = 'folder_policy.v1'
    audio = [ordered]@{ transcode_bitrate = '0k' }
})
$zeroBitrateOverrides = ConvertTo-MediaPipelineFolderPolicyOverrides -Policy $zeroBitratePolicy -PolicyPath 'C:\Media\mediapipeline.folder.json'
Assert-True (-not $zeroBitrateOverrides.ContainsKey('AudioTranscodeBitrate')) 'Folder policy must not promote zero audio transcode bitrate overrides.'
$fallbackRemuxPolicy = Convert-RoundTripJson ([ordered]@{
    schema_version = 'folder_policy.v1'
    routing = [ordered]@{ size_guard_mode = 'fallback_remux' }
})
$fallbackRemuxOverrides = ConvertTo-MediaPipelineFolderPolicyOverrides -Policy $fallbackRemuxPolicy -PolicyPath 'C:\Media\mediapipeline.folder.json'
Assert-Equal $fallbackRemuxOverrides.SizeGuardMode 'fallback_remux' 'Folder policy must preserve fallback_remux size guard mode.'
$pythonWrittenTopology = Convert-RoundTripJson ([ordered]@{
    audio = @(@('eac3', 'eng', 6))
    subtitles = @(@('ass', 'eng'))
})
$objectWrittenTopology = [ordered]@{
    audio = @([ordered]@{ codec = 'eac3'; language = 'eng'; channels = 6 })
    subtitles = @([ordered]@{ codec = 'ass'; language = 'eng' })
}
Assert-True (Test-FolderPolicyTopologyMatches -Expected $pythonWrittenTopology -Actual $objectWrittenTopology) 'Folder policy topology should accept JSON-array and object/dictionary item shapes.'

$folderPolicyRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-folder-policy-root-' + [guid]::NewGuid().ToString('N'))
try {
    $sourceMovies = Join-Path $folderPolicyRoot 'Movies'
    $sourceTv = Join-Path $folderPolicyRoot 'TV'
    $insideSeason = Join-Path $sourceTv 'Show\Season 01'
    $outside = Join-Path $folderPolicyRoot 'Outside'
    New-Item -ItemType Directory -Path $sourceMovies, $insideSeason, $outside -Force | Out-Null
    $insideSource = Join-Path $insideSeason 'Show - S01E01.mkv'
    $outsideSource = Join-Path $outside 'Outside.mkv'
    Set-Content -LiteralPath $insideSource -Value 'media' -Encoding UTF8
    Set-Content -LiteralPath $outsideSource -Value 'media' -Encoding UTF8
    $policyJson = [ordered]@{
        schema_version = 'folder_policy.v1'
        audio = [ordered]@{ preferred_default_languages = @('jpn') }
    } | ConvertTo-Json -Depth 5
    Set-Content -LiteralPath (Join-Path $sourceTv 'mediapipeline.folder.json') -Value $policyJson -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $outside 'mediapipeline.folder.json') -Value $policyJson -Encoding UTF8

    $script:SourceMovies = $sourceMovies
    $script:SourceTV = $sourceTv
    $outsideOverrides = Resolve-FolderPolicyOverrides -SourceFile $outsideSource
    Assert-True ($null -eq $outsideOverrides) 'Folder policy sidecar outside configured source roots must not be applied.'
    $insideOverrides = Resolve-FolderPolicyOverrides -SourceFile $insideSource
    Assert-True ($null -ne $insideOverrides) 'Folder policy sidecar inside source root should be discovered by parent climb.'
    Assert-Equal $insideOverrides['PreferredDefaultAudioLanguages'][0] 'jpn' 'Inside folder policy audio override not applied.'
} finally {
    Remove-Item -LiteralPath $folderPolicyRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Variable -Name SourceMovies -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name SourceTV -Scope Script -ErrorAction SilentlyContinue
}

Write-Host "OK: contract schema checks passed."
