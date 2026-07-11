[CmdletBinding()]
param(
    [string]$LibraryRoot = '',
    [string[]]$LibraryRoots = @(),
    [string]$ConfigPath = '',
    [string]$ReportRoot,
    [switch]$IncludeSidecars,
    [switch]$EmitText,
    [switch]$EmitJson,
    [switch]$EmitCsv,
    [switch]$RebuildProbeCache,
    [string]$ScorePolicyPath = '',
    [string]$IgnoreManifestPath = '',
    [ValidateRange(5, 3600)]
    [int]$FfprobeTimeoutSeconds = 60,
    [ValidateRange(1, 8)]
    [int]$ProbeConcurrency = 2,
    [ValidateRange(30, 86400)]
    [int]$AuditEnumerationTimeoutSeconds = 1800,
    [switch]$AllowSystemTools
)

$script:ProductVersion = '2026.06.04.001'
$script:PipelineRoot = if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { Split-Path -Parent (Get-Location).Path }
if ($PSScriptRoot) {
    $versioningModule = Join-Path $script:PipelineRoot 'engine\shared\versioning.ps1'
    if (Test-Path -LiteralPath $versioningModule -PathType Leaf) {
        . $versioningModule
        $script:ProductVersion = Get-MediaPipelineProductVersion
    }
}
$script:AuditVersion = '1.0'
$script:CurrentPipelineVersion = '1.0'
$script:AuditStartedAt = (Get-Date -Format 'o')
$script:AuditProgressPath = $null
$script:AuditProgressProcessed = 0
$script:AuditProgressTotal = 0
$script:AuditReportStage = ''
$script:AuditReportStepIndex = 0
$script:AuditReportStepTotal = 0
$script:AuditReportSteps = @()
$script:AuditReportCompletedSteps = @()
$script:AuditProgressLastWriteUtc = $null
$script:AuditProgressLastProcessed = -1
$script:AuditProgressMinIntervalMs = 1000
$script:AuditProgressMinFileDelta = 25
$script:AuditProgressWriteFailures = 0
$script:AuditProgressPersistenceHealthy = $true
$script:ProbeCacheSchemaVersion = '2'
$script:ProbeCacheFieldSetVersion = 'ffprobe-v2-format=format_name,duration-stream=index,codec_type,codec_name,codec_long_name,codec_tag_string,codec_tag,channels-tags=language,title-disposition=default,forced'
$script:ProbeCacheRoot = $null
$script:ProbeCacheHitCount = 0
$script:ProbeCacheMissCount = 0
$script:ProbeCacheWriteCount = 0
$script:AuditProbeConcurrency = [int]$ProbeConcurrency
$script:AuditRebuildProbeCache = [bool]$RebuildProbeCache
$script:AuditAllowSystemTools = [bool]$AllowSystemTools
$script:AuditScorePolicyPath = $ScorePolicyPath
$script:AuditIgnoreManifestPath = $IgnoreManifestPath
$script:AuditScorePolicy = $null
$script:AuditIgnoreEntries = @{}

if (-not $PSBoundParameters.ContainsKey('IncludeSidecars')) { $IncludeSidecars = $false }
if (-not $PSBoundParameters.ContainsKey('EmitText')) { $EmitText = $false }
if (-not $PSBoundParameters.ContainsKey('EmitJson')) { $EmitJson = $true }
if (-not $PSBoundParameters.ContainsKey('EmitCsv')) { $EmitCsv = $true }

$script:AuditModuleRoot = Join-Path $PSScriptRoot 'Modules'
foreach ($auditModuleName in @(
    'MediaConstants.ps1',
    'Versioning.ps1',
    'QueuePlan.ps1',
    'Naming.ps1',
    'Audit.Progress.ps1',
    'Audit.Policy.ps1',
    'Audit.Probe.ps1',
    'Audit.Reports.ps1',
    'Audit.Scanner.ps1'
)) {
    $auditModulePath = switch ($auditModuleName) {
        'MediaConstants.ps1' { Join-Path $script:PipelineRoot 'engine\shared\media_constants.ps1' }
        'Versioning.ps1' { Join-Path $script:PipelineRoot 'engine\shared\versioning.ps1' }
        'Audit.Progress.ps1' { Join-Path $script:PipelineRoot 'engine\audit\progress.ps1' }
        'Audit.Policy.ps1' { Join-Path $script:PipelineRoot 'engine\audit\policy.ps1' }
        'Audit.Probe.ps1' { Join-Path $script:PipelineRoot 'engine\audit\probe.ps1' }
        'Audit.Reports.ps1' { Join-Path $script:PipelineRoot 'engine\audit\reports.ps1' }
        'Audit.Scanner.ps1' { Join-Path $script:PipelineRoot 'engine\audit\scanner.ps1' }
        'Naming.ps1' { Join-Path $script:PipelineRoot 'engine\naming\naming.ps1' }
        'QueuePlan.ps1' { Join-Path $script:PipelineRoot 'engine\queue\queue_plan.ps1' }
        default { Join-Path $script:AuditModuleRoot $auditModuleName }
    }
    if (-not (Test-Path -LiteralPath $auditModulePath)) {
        throw "Required audit module was not found: $auditModulePath"
    }
    . $auditModulePath
}

foreach ($auditSliceName in @(
    'path_utilities.ps1',
    'scanner.ps1'
)) {
    $auditSlicePath = Join-Path (Join-Path $PSScriptRoot 'Audit-MediaLibrary') $auditSliceName
    if (-not (Test-Path -LiteralPath $auditSlicePath)) {
        throw "Required audit slice was not found: $auditSlicePath"
    }
    . $auditSlicePath
}

$script:ProductVersion = Get-MediaPipelineProductVersion
$script:AuditVersion = Get-MediaPipelineAuditSchemaVersion
$script:CurrentPipelineVersion = Get-MediaPipelineSidecarVersion

$script:SidecarIssueCodes = @(
    'missing-sidecar',
    'invalid-sidecar-json',
    'sidecar-missing-version',
    'sidecar-invalid-version',
    'sidecar-stale-version',
    'sidecar-output-mismatch',
    'sidecar-missing-route'
)

$script:HighPriorityIssueCodes = @(
    'ffprobe-open-failed',
    'missing-video-stream',
    'missing-audio-stream',
    'audio-multiple-defaults',
    'audio-default-policy-mismatch',
    'subtitle-multiple-defaults',
    'audio-missing-explicit-default',
    'commentary-default-audio',
    'tx3g-extraction-failed',
    'bdpgs-ocr-failed',
    'vobsub-ocr-failed',
    'foreign-audio-no-subtitles',
    'foreign-audio-no-text-subtitles'
)

$script:MediumPriorityIssueCodes = @(
    'multiple-video-streams',
    'audio-track-titles-missing',
    'subtitle-track-titles-missing',
    'default-audio-language-unknown',
    'default-subtitle-language-unknown',
    'default-audio-may-transcode',
    'default-ass-subtitle',
    'ass-only-subtitles',
    'tx3g-only-subtitles',
    'tx3g-subtitles-extractable',
    'bdpgs-only-subtitles',
    'bdpgs-subtitles-ocr-candidate',
    'vobsub-only-subtitles',
    'vobsub-subtitles-ocr-candidate',
    'default-image-subtitle',
    'image-only-subtitles',
    'audio-language-tags-unknown',
    'subtitle-language-tags-unknown',
    'ambiguous-tv-naming'
)

$script:AuditScorePolicy = Import-AuditScorePolicy -Path $script:AuditScorePolicyPath
$script:AuditIgnoreEntries = Import-AuditIgnoreManifest -Path $script:AuditIgnoreManifestPath

. (Join-Path $PSScriptRoot '..\engine\audit\command_support.ps1')
. (Join-Path $PSScriptRoot '..\engine\audit\media_evidence.ps1')
. (Join-Path $PSScriptRoot '..\engine\audit\library_lookup.ps1')
. (Join-Path $PSScriptRoot '..\engine\audit\result_analysis.ps1')



























































# Remove-PriorityMarkersFromName, Normalize-TVShowFolderName,
# Get-TVEpisodeFromFilename, Get-TVFolderSeasonInfo, and Get-TVInfoFromFile
# are provided by ops\pipeline\engine\queue\queue_plan.ps1 and ops\pipeline\engine\naming\naming.ps1, which are
# loaded in the module-loading loop above.  The inline copies that used to
# live here were removed to eliminate drift; the canonical versions in those
# modules now handle ordinal-season folders, extras-container detection,
# multi-episode filenames, and stripped-name episode extraction.

















try {
    $script:ConfigPathResolved = $null
    $config = $null
    if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
        # Default lookup: prefer current convention, fall back to legacy `_chatgpt` name.
        foreach ($candidate in @(
            (Join-Path $script:PipelineRoot 'config\MediaPipeline_config.psd1'),
            (Join-Path $script:PipelineRoot 'config\MediaPipeline_config_chatgpt.psd1'),
            (Join-Path $PSScriptRoot 'MediaPipeline_config.psd1'),
            (Join-Path $PSScriptRoot 'MediaPipeline_config_chatgpt.psd1')
        )) {
            $probe = $candidate
            if (Test-Path -LiteralPath $probe) { $ConfigPath = $probe; break }
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($ConfigPath) -and (Test-Path -LiteralPath $ConfigPath)) {
        $script:ConfigPathResolved = Resolve-ExistingPath $ConfigPath
        $config = Import-PowerShellDataFile -LiteralPath $script:ConfigPathResolved
    }

    $libraryRootInputs = [System.Collections.Generic.List[string]]::new()
    foreach ($candidateRoot in @($LibraryRoots)) {
        if (-not [string]::IsNullOrWhiteSpace($candidateRoot)) {
            $libraryRootInputs.Add([string]$candidateRoot) | Out-Null
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($LibraryRoot)) {
        $libraryRootInputs.Add([string]$LibraryRoot) | Out-Null
    }
    if ($libraryRootInputs.Count -eq 0) {
        $defaultLibraryRoot = Get-AuditDefaultLibraryRootFromConfig -Config $config
        if (-not [string]::IsNullOrWhiteSpace($defaultLibraryRoot)) {
            $libraryRootInputs.Add([string]$defaultLibraryRoot) | Out-Null
        }
    }
    if ($libraryRootInputs.Count -eq 0) {
        throw "LibraryRoot was not provided. Pass -LibraryRoot explicitly or set SourceMovies/SourceTV in the config with a shared parent root."
    }

    $resolvedLibraryRoots = [System.Collections.Generic.List[string]]::new()
    $seenLibraryRoots = @{}
    foreach ($candidateRoot in @($libraryRootInputs)) {
        $resolvedRoot = Resolve-ExistingPath $candidateRoot
        if (-not (Test-IsUncPath $resolvedRoot) -and -not (Test-Path -LiteralPath $resolvedRoot)) {
            throw "Library root was not found: $candidateRoot"
        }
        $rootKey = ([string]$resolvedRoot -replace '[\\/]+$','').ToLowerInvariant()
        if ($seenLibraryRoots.ContainsKey($rootKey)) {
            continue
        }
        $seenLibraryRoots[$rootKey] = $true
        $resolvedLibraryRoots.Add([string]$resolvedRoot) | Out-Null
    }
    if ($resolvedLibraryRoots.Count -eq 0) {
        throw "No unique audit library roots were available."
    }
    $script:LibraryRootsResolved = @($resolvedLibraryRoots)
    $script:LibraryRootResolved = $script:LibraryRootsResolved[0]

    if ($config -and $config.ContainsKey('AllowSystemTools')) {
        try {
            $script:AuditAllowSystemTools = [bool]$config.AllowSystemTools -or [bool]$AllowSystemTools
        } catch {
            $script:AuditAllowSystemTools = [bool]$AllowSystemTools
        }
    }

    $script:PriorityMarkers = @('!', '[NOW]')
    if ($config -and $config.ContainsKey('PriorityMarkers') -and @($config.PriorityMarkers).Count -gt 0) {
        $script:PriorityMarkers = @($config.PriorityMarkers | ForEach-Object { [string]$_ })
    }

    $script:CompatibleAudioCodecs = @('aac','ac3','eac3','mp3','opus','vorbis','flac','truehd','mlp')
    if ($config -and $config.ContainsKey('CompatibleAudioCodecs') -and @($config.CompatibleAudioCodecs).Count -gt 0) {
        $script:CompatibleAudioCodecs = @($config.CompatibleAudioCodecs | ForEach-Object { ([string]$_).ToLowerInvariant() })
    }

    $script:PreferredDefaultAudioLanguages = @('english')
    if ($config -and $config.ContainsKey('PreferredDefaultAudioLanguages') -and @($config.PreferredDefaultAudioLanguages).Count -gt 0) {
        $script:PreferredDefaultAudioLanguages = @($config.PreferredDefaultAudioLanguages | ForEach-Object { [string]$_ })
    }

    $script:ValidExtensions = @('.mkv', '.mp4', '.avi', '.mov', '.m4v', '.ts', '.m2ts')
    if ($config -and $config.ContainsKey('ValidExtensions') -and @($config.ValidExtensions).Count -gt 0) {
        $script:ValidExtensions = @($config.ValidExtensions | ForEach-Object { ([string]$_).ToLowerInvariant() })
    }

    $script:MinPipelineVersion = $script:CurrentPipelineVersion
    if ($config -and $config.ContainsKey('MinPipelineVersion') -and $config.MinPipelineVersion) {
        $candidate = [string]$config.MinPipelineVersion
        if (Test-PipelineVersionString $candidate) {
            if (Compare-PipelineVersion $script:CurrentPipelineVersion $candidate) {
                $script:MinPipelineVersion = $script:CurrentPipelineVersion
            } else {
                $script:MinPipelineVersion = $candidate
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace($ReportRoot)) {
        if ($config -and $config.ContainsKey('LocalBase') -and $config.LocalBase) {
            $ReportRoot = Join-Path ([string]$config.LocalBase) 'AuditReports'
        } else {
            $ReportRoot = Join-Path $PSScriptRoot 'AuditReports'
        }
    }
    $script:ReportRootResolved = Resolve-ExistingPath $ReportRoot
    if (-not (Test-Path -LiteralPath $script:ReportRootResolved)) {
        New-Item -ItemType Directory -Path $script:ReportRootResolved -Force | Out-Null
    }
    $script:AuditProgressPath = Join-Path $script:ReportRootResolved 'audit_progress.json'
    $script:ProbeCacheRoot = Join-Path $script:ReportRootResolved 'ProbeCache'
    if (-not (Test-Path -LiteralPath $script:ProbeCacheRoot)) {
        New-Item -ItemType Directory -Path $script:ProbeCacheRoot -Force | Out-Null
    }
    Test-AuditProgressPersistence | Out-Null
    if ($script:AuditRebuildProbeCache) {
        Clear-ProbeCache
        if (-not (Test-Path -LiteralPath $script:ProbeCacheRoot)) {
            New-Item -ItemType Directory -Path $script:ProbeCacheRoot -Force | Out-Null
        }
    }

    $script:FfprobePath = Resolve-ExecutablePath -Name 'ffprobe' -RelativeCandidates @('..\tools\ffmpeg\bin\ffprobe.exe', 'Tools\ffmpeg\bin\ffprobe.exe')

    Write-AuditLog "===== LIBRARY AUDIT START $($script:ProductVersion) (audit $($script:AuditVersion)) ====="
    Write-AuditLog "Library root count : $(@($script:LibraryRootsResolved).Count)"
    foreach ($resolvedRoot in @($script:LibraryRootsResolved)) {
        Write-AuditLog "Library root       : $resolvedRoot"
    }
    Write-AuditLog "Report root        : $($script:ReportRootResolved)"
    Write-AuditLog "Product ver        : $($script:ProductVersion)"
    Write-AuditLog "Probe cache root   : $($script:ProbeCacheRoot)"
    Write-AuditLog "Config path        : $(if ($script:ConfigPathResolved) { $script:ConfigPathResolved } else { '(none)' })"
    Write-AuditLog "ffprobe            : $($script:FfprobePath)"
    Write-AuditLog "Probe concurrency   : $($script:AuditProbeConcurrency)"
    Write-AuditLog "Enumeration timeout: $($AuditEnumerationTimeoutSeconds)s"
    Write-AuditLog "Progress health    : $(if ($script:AuditProgressPersistenceHealthy) { 'healthy' } else { 'unavailable' })"
    Write-AuditLog "Include sidecars   : $IncludeSidecars"
    Write-AuditLog "Rebuild probe cache: $($script:AuditRebuildProbeCache)"
    Write-AuditLog "Min pipeline ver   : $($script:MinPipelineVersion)"
    Write-AuditProgress -Status 'starting' -ProcessedFiles 0 -TotalFiles 0 -CurrentOperation 'Initializing audit run.'

    Write-AuditProgress -Status 'starting' -ProcessedFiles 0 -TotalFiles 0 -CurrentOperation 'Enumerating media files.'
    $rootMediaBatches = [System.Collections.Generic.List[object]]::new()
    $totalMediaFiles = 0
    foreach ($resolvedRoot in @($script:LibraryRootsResolved)) {
        $script:LibraryRootResolved = $resolvedRoot
        Write-AuditProgress -Status 'starting' -ProcessedFiles 0 -TotalFiles $totalMediaFiles -CurrentOperation "Enumerating media files under $resolvedRoot."
        $mediaFiles = @(Get-AuditMediaFilesBounded -RootPath $resolvedRoot -TimeoutSeconds $AuditEnumerationTimeoutSeconds)
        $rootMediaBatches.Add([pscustomobject]@{
            RootPath   = $resolvedRoot
            MediaFiles = @($mediaFiles)
        }) | Out-Null
        $totalMediaFiles += $mediaFiles.Count
        Write-AuditLog "Media files found  : $($mediaFiles.Count) under $resolvedRoot"
    }

    Write-AuditLog "Media files total  : $totalMediaFiles"
    Write-AuditProgress -Status 'scanning' -ProcessedFiles 0 -TotalFiles $totalMediaFiles -CurrentOperation 'Enumerated media files.'

    $allResults = [System.Collections.Generic.List[object]]::new()
    foreach ($batch in @($rootMediaBatches)) {
        $script:LibraryRootResolved = [string]$batch.RootPath
        Write-AuditLog "Scanning root      : $($script:LibraryRootResolved)"
        $batchResults = @(Invoke-AuditFileScan -MediaFiles @($batch.MediaFiles) -LibraryRoot $script:LibraryRootResolved)
        foreach ($item in @($batchResults)) {
            $allResults.Add($item) | Out-Null
        }
    }
    $script:LibraryRootResolved = if (@($script:LibraryRootsResolved).Count -eq 1) { $script:LibraryRootsResolved[0] } else { @($script:LibraryRootsResolved) -join '; ' }
    $total = $allResults.Count
    $results = @($allResults)
    Write-AuditProgress -Status 'writing-reports' -ProcessedFiles $total -TotalFiles $total -CurrentOperation 'Writing report files.'

    $reportBundle = Write-AuditReportBundle -Results @($results) -EmitText ([bool]$EmitText) -EmitJson ([bool]$EmitJson) -EmitCsv ([bool]$EmitCsv)
    $bucketCounts = $reportBundle.BucketCounts

    Write-AuditLog "Probe cache stats  : hits $($script:ProbeCacheHitCount) | misses $($script:ProbeCacheMissCount) | writes $($script:ProbeCacheWriteCount)"

    Write-AuditProgress `
        -Status 'completed' `
        -ProcessedFiles $total `
        -TotalFiles $total `
        -CurrentOperation 'Audit complete.' `
        -Completed $true `
        -LatestCsvPath $reportBundle.CsvPath `
        -LatestPriorityCsvPath $reportBundle.PriorityCsvPath `
        -LatestJsonPath $reportBundle.JsonPath `
        -LatestTextPath $reportBundle.TextPath
    Write-AuditLog ("Scan complete: OK={0}, REVIEW={1}, RERUN_PIPELINE={2}, REDOWNLOAD_CANDIDATE={3}, IGNORED={4}" -f $bucketCounts.OK, $bucketCounts.REVIEW, $bucketCounts.RERUN_PIPELINE, $bucketCounts.REDOWNLOAD_CANDIDATE, $bucketCounts.IGNORED)
    Write-AuditLog "===== LIBRARY AUDIT END ====="
} catch {
    Complete-AuditConsoleProgress
    Write-AuditProgress -Status 'failed' -ProcessedFiles $script:AuditProgressProcessed -TotalFiles $script:AuditProgressTotal -CurrentOperation $_.Exception.Message -Completed $true -Failed $true
    Write-AuditLog $_.Exception.Message 'ERROR'
    exit 1
}
