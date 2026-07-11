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

$completedSchema = Get-Content -LiteralPath (Join-Path $schemasRoot 'media_pipeline_completed_job.schema.json') -Raw | ConvertFrom-Json -ErrorAction Stop
$pendingSchema = Get-Content -LiteralPath (Join-Path $schemasRoot 'media_pipeline_pending_push_manifest.schema.json') -Raw | ConvertFrom-Json -ErrorAction Stop
$subtitleEvidenceFields = @(
    'tx3g_srt_tracks',
    'tx3g_srt_failures',
    'bdpgs_srt_failures',
    'vobsub_srt_failures',
    'converted_srt_sidecar_candidates',
    'subtitle_output_reduction',
    'tx3g_embedded_srt_tracks',
    'bdpgs_embedded_srt_tracks',
    'vobsub_embedded_srt_tracks'
)
foreach ($field in $subtitleEvidenceFields) {
    $completedProperty = $completedSchema.properties.PSObject.Properties[$field]
    Assert-True ($null -ne $completedProperty) "Completed-job schema missing subtitle evidence field: $field"
    Assert-Equal $completedProperty.Value.type 'array' "Completed-job subtitle evidence field should be an array: $field"
    $pendingProperty = $pendingSchema.properties.PSObject.Properties[$field]
    Assert-True ($null -ne $pendingProperty) "Pending manifest schema missing subtitle evidence field: $field"
    Assert-Equal $pendingProperty.Value.type 'array' "Pending manifest subtitle evidence field should be an array: $field"
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
    converted_srt_sidecar_candidates = @([ordered]@{ source_subtitle_kind = 'ass'; selected = $true })
    subtitle_output_reduction = @([ordered]@{ source_subtitle_kind = 'tx3g'; selected = $false; reduction_reason = 'mp4_compatibility_selected_single_external_srt_sidecar' })
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
Assert-Equal @($pendingManifest.converted_srt_sidecar_candidates).Count 1 'Pending manifest MP4 subtitle candidate evidence did not round-trip.'
Assert-Equal @($pendingManifest.subtitle_output_reduction).Count 1 'Pending manifest MP4 subtitle reduction evidence did not round-trip.'
Assert-True ([bool]$pendingManifest.vobsub_srt_conversion_enabled) 'Pending manifest VobSub conversion flag did not round-trip.'

$rerunCsvScriptText = (@(
        'engine\rerun\entry_support.ps1',
        'engine\rerun\evidence.ps1',
        'engine\rerun\planning.ps1',
        'engine\rerun\publish.ps1',
        'entrypoints\Invoke-RerunCsv.ps1'
    ) | ForEach-Object { Get-Content -LiteralPath (Join-Path $pipelineRoot $_) -Raw }) -join "`n"
foreach ($field in @(
    'product_version',
    'pipeline_version',
    'publish_transaction_id',
    'manifest_state',
    'local_file',
    'server_out',
    'route',
    'source_identity_v2',
    'source_identity_v2_algorithm',
    'source_path',
    'output_size',
    'sidecar_files',
    'tx3g_srt_tracks',
    'tx3g_srt_failures',
    'bdpgs_srt_failures',
    'vobsub_srt_failures',
    'converted_srt_sidecar_candidates',
    'subtitle_output_reduction',
    'tx3g_embedded_srt_tracks',
    'bdpgs_embedded_srt_tracks',
    'vobsub_embedded_srt_tracks'
)) {
    Assert-True ($rerunCsvScriptText -match "(?m)^\s*$([regex]::Escape($field))\s*=") "CSV rerun pending-publish writer missing current manifest field: $field"
}
Assert-True ($rerunCsvScriptText.Contains("manifest_state = 'pending_move'")) 'CSV rerun pending-publish writer must write pending_move before moving media.'
Assert-True ($rerunCsvScriptText.Contains('$payload[''manifest_state''] = ''parked''')) 'CSV rerun pending-publish writer must update manifest to parked after moving media.'
Assert-True ($rerunCsvScriptText.Contains('function New-RerunPendingSidecarEntries')) 'CSV rerun pending-publish writer must preserve sibling sidecar files.'
Assert-True ($rerunCsvScriptText.Contains('function Get-RerunPendingServerDestinationSet')) 'CSV rerun pending-publish writer must inspect existing pending server destinations before parking.'
Assert-True ($rerunCsvScriptText.Contains('return ,$set')) 'CSV rerun pending server destination set must return as a single HashSet, not an enumerated fixed-size array.'
Assert-True ($rerunCsvScriptText.Contains('function Resolve-RerunPendingPublishServerOut')) 'CSV rerun pending-publish writer must resolve server_out collision policy before writing a manifest.'
Assert-True ($rerunCsvScriptText.Contains('-ServerOut $serverOut')) 'CSV rerun pending-publish writer must pass the resolved server_out into manifest creation.'
Assert-True ($rerunCsvScriptText.Contains('server_out = $ServerOut')) 'CSV rerun pending-publish manifests must store the resolved server_out, not the unadjusted planned destination.'
Assert-True ($rerunCsvScriptText.Contains('CSV rerun original source policies are disabled')) 'CSV rerun must fail closed for original source mutation policies.'

$completedJob = Convert-RoundTripJson ([ordered]@{
    schema_version   = 'pipeline_sidecar.v1'
    pipeline_version = '4'
    created_at       = '2026-05-06T12:00:00Z'
    encoded_at       = '2026-05-06T12:00:00Z'
    logged_at        = '2026-05-06T12:01:00Z'
    route            = 'encode'
    output_file      = 'Movie.mkv'
    output_path      = '\\server\Movies\Movie.mkv'
    tx3g_srt_tracks  = @([ordered]@{ language = 'eng' })
    tx3g_srt_failures = @()
    bdpgs_srt_failures = @()
    vobsub_srt_failures = @([ordered]@{ reason = 'ocr unavailable' })
    converted_srt_sidecar_candidates = @([ordered]@{ source_subtitle_kind = 'ass'; selected = $true })
    subtitle_output_reduction = @([ordered]@{ source_subtitle_kind = 'tx3g'; selected = $false })
    tx3g_embedded_srt_tracks = @([ordered]@{ language = 'eng' })
    bdpgs_embedded_srt_tracks = @()
    vobsub_embedded_srt_tracks = @([ordered]@{ language = 'eng' })
})
Assert-Equal $completedJob.schema_version 'pipeline_sidecar.v1' 'Completed manifest compatibility schema mismatch.'
Assert-Equal @($completedJob.vobsub_srt_failures).Count 1 'Completed manifest VobSub failure evidence did not round-trip.'
Assert-Equal @($completedJob.vobsub_embedded_srt_tracks).Count 1 'Completed manifest VobSub embedded evidence did not round-trip.'
Assert-Equal @($completedJob.subtitle_output_reduction).Count 1 'Completed manifest MP4 reduction evidence did not round-trip.'

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
