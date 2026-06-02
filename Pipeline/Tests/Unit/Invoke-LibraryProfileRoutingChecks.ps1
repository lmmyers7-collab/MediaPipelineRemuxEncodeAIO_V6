param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
. (Join-Path $repoRoot 'engine\paths\output_path_planning.ps1')
. (Join-Path $repoRoot 'engine\shared\path_helpers.ps1')
. (Join-Path $repoRoot 'engine\queue\queue_plan.ps1')
. (Join-Path $repoRoot 'engine\queue\file_overrides.ps1')
. (Join-Path $repoRoot 'engine\library\library_index.ps1')
. (Join-Path $repoRoot 'engine\config\config_schema.ps1')

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
    if ($null -ne $script:CapturedLogs) {
        $script:CapturedLogs.Add([pscustomobject]@{ Message = $Message; Level = $Level }) | Out-Null
    }
}

function Invoke-RecursivePathScan {
    param([string] $Path, [string] $ItemType = 'File', [int] $TimeoutSeconds = 0, [string] $Label = '')
    return @(Get-ChildItem -LiteralPath $Path -File -Recurse | ForEach-Object { $_.FullName })
}

function Start-StopAwareSleep {
    param([int] $Seconds)
    return $true
}

function Assert-Equal {
    param(
        [Parameter(Mandatory)] $Actual,
        [Parameter(Mandatory)] $Expected,
        [Parameter(Mandatory)] [string] $Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected' but got '$Actual'."
    }
}

function Assert-Contains {
    param(
        [Parameter(Mandatory)] $Items,
        [Parameter(Mandatory)] $Expected,
        [Parameter(Mandatory)] [string] $Message
    )
    if (-not (@($Items) -contains $Expected)) {
        throw "$Message Expected collection to contain '$Expected'."
    }
}

function Assert-True {
    param(
        [Parameter(Mandatory)] [bool] $Condition,
        [Parameter(Mandatory)] [string] $Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-Throws {
    param(
        [Parameter(Mandatory)] [scriptblock] $ScriptBlock,
        [Parameter(Mandatory)] [string] $Message,
        [string] $ExpectedText = ''
    )
    try {
        & $ScriptBlock
    } catch {
        if (-not [string]::IsNullOrWhiteSpace($ExpectedText) -and ([string]$_.Exception.Message) -notmatch [regex]::Escape($ExpectedText)) {
            throw "$Message Expected error text '$ExpectedText' but got '$($_.Exception.Message)'."
        }
        return
    }
    throw $Message
}

$script:CapturedLogs = [System.Collections.Generic.List[object]]::new()

$script:SourceMovies = 'C:\Incoming\Movies'
$script:SourceTV = 'C:\Incoming\TV'
$script:Outsource = 'D:\Processed'
$script:OutputContainer = 'mkv'
$script:RoutingProfile = 'plex_direct_stream'
$script:VideoQuality = 22
$script:AudioMaxChannels = 8
$script:LibraryProfiles = @(
    [pscustomobject]@{
        id = 'movies'
        name = 'Movies'
        enabled = $true
        designation = 'movie'
        source_path = 'C:\Incoming\Movies'
        output_path = 'D:\Processed'
        promotion_enabled = $false
        promotion_destination = ''
        overrides = [pscustomobject]@{
            editor = [pscustomobject]@{ RoutingProfile = 'manual'; OutputContainer = 'mp4' }
            video = [pscustomobject]@{ VideoQuality = 19 }
            subtitles = [pscustomobject]@{ SubKeepLanguages = @('eng','und') }
            audio = [pscustomobject]@{ AudioMaxChannels = 2 }
        }
    },
    [pscustomobject]@{
        id = 'anime'
        name = 'Anime'
        enabled = $true
        designation = 'tv'
        source_path = 'E:\AnimeSource'
        output_path = 'F:\AnimeProcessed'
        promotion_enabled = $true
        promotion_destination = 'G:\FinalAnime'
        overrides = [pscustomobject]@{
            editor = [pscustomobject]@{ RoutingProfile = 'archive_quality' }
            audio = [pscustomobject]@{ AudioMaxChannels = 6 }
        }
    }
)

$movieOverrides = Resolve-MediaPipelineLibraryOverridesForPath -SourcePath 'C:\Incoming\Movies\Movie.mkv'
Assert-Equal $movieOverrides['RoutingProfile'] 'manual' 'Expected Movies library routing override.'
Assert-Equal $movieOverrides['VideoQuality'] 19 'Expected Movies video override.'
Assert-Equal $movieOverrides['AudioMaxChannels'] 2 'Expected Movies audio override.'
Assert-Contains $movieOverrides.Keys 'SubKeepLanguages' 'Expected Movies subtitle override key.'

$animeOverrides = Resolve-MediaPipelineLibraryOverridesForPath -SourcePath 'E:\AnimeSource\Show\Season 01\Show - S01E01.mkv'
Assert-Equal $animeOverrides['RoutingProfile'] 'archive_quality' 'Expected Anime library routing override.'
Assert-Equal $animeOverrides['AudioMaxChannels'] 6 'Expected Anime library audio override.'

$snapshot = Push-MediaPipelineActiveConfigOverrides -Overrides $movieOverrides
try {
    Assert-Equal $script:RoutingProfile 'manual' 'Expected active config push to override RoutingProfile.'
    Assert-Equal $script:VideoQuality 19 'Expected active config push to override VideoQuality.'
    Assert-Equal $script:AudioMaxChannels 2 'Expected active config push to override AudioMaxChannels.'
} finally {
    Pop-MediaPipelineActiveConfigOverrides -Snapshot $snapshot
}
Assert-Equal $script:RoutingProfile 'plex_direct_stream' 'Expected active config pop to restore RoutingProfile.'
Assert-Equal $script:VideoQuality 22 'Expected active config pop to restore VideoQuality.'
Assert-Equal $script:AudioMaxChannels 8 'Expected active config pop to restore AudioMaxChannels.'

$legacyProfile = [pscustomobject]@{
    editor_overrides = [pscustomobject]@{ RoutingProfile = 'manual' }
    media_overrides = [pscustomobject]@{ VideoQuality = 18; AudioMaxChannels = 4 }
}
$legacyOverrides = Get-MediaPipelineLibraryProfileOverrideMap -Profile $legacyProfile
Assert-Equal $legacyOverrides['RoutingProfile'] 'manual' 'Expected legacy editor override compatibility.'
Assert-Equal $legacyOverrides['VideoQuality'] 18 'Expected legacy media video override compatibility.'
Assert-Equal $legacyOverrides['AudioMaxChannels'] 4 'Expected legacy media audio override compatibility.'

$animeEvidence = Get-MediaPipelineLibraryProfileEvidenceForPath -SourcePath 'E:\AnimeSource\Show\Season 01\Show - S01E01.mkv'
Assert-Equal $animeEvidence['library_id'] 'anime' 'Expected longest matching library profile evidence.'
Assert-Equal $animeEvidence['designation'] 'tv' 'Expected TV designation to carry through profile evidence.'
Assert-Equal $animeEvidence['output_root'] 'F:\AnimeProcessed' 'Expected per-library output root.'
Assert-Equal $animeEvidence['promotion_enabled'] $true 'Expected promotion enabled state to carry through profile evidence.'
Assert-Equal $animeEvidence['promotion_destination_root'] 'G:\FinalAnime' 'Expected promotion destination root to carry through profile evidence.'
Assert-Equal $animeEvidence['promotion_rule_id'] 'library-profile-anime' 'Expected profile-derived promotion rule id in profile evidence.'
Assert-Equal $animeEvidence['promotion_rule_source'] 'profile_derived' 'Expected promotion rule source to identify profile-derived authority.'
Assert-Contains $animeEvidence['settings_override_keys'] 'AudioMaxChannels' 'Expected evidence to include settings override keys.'
Assert-Equal $animeEvidence['settings_overrides']['AudioMaxChannels'] 6 'Expected evidence to include explicit settings override values.'
Assert-Equal $animeEvidence['effective_settings']['AudioMaxChannels'] 6 'Expected evidence to include resolved effective library settings.'
Assert-Equal $animeEvidence['effective_settings']['OutputContainer'] 'mkv' 'Expected missing library override fields to inherit global config in evidence.'
Assert-True (-not $animeEvidence['effective_settings'].Contains('FolderPolicyPath')) 'Expected library_effective_settings to exclude folder policy metadata.'
Assert-True (-not $animeEvidence['effective_settings'].Contains('_FileOverride')) 'Expected library_effective_settings to exclude per-file override metadata.'
Assert-True (-not $animeEvidence['effective_settings'].Contains('source_codec')) 'Expected library_effective_settings to exclude source/probe facts.'

$movieEvidence = Get-MediaPipelineLibraryProfileEvidenceForPath -SourcePath 'C:\Incoming\Movies\Movie.mkv'
Assert-Equal $movieEvidence['promotion_enabled'] $false 'Expected disabled promotion state to carry through profile evidence.'
Assert-Equal $movieEvidence['promotion_destination_root'] '' 'Expected disabled promotion evidence not to emit a destination root.'
Assert-Equal $movieEvidence['promotion_rule_id'] '' 'Expected disabled promotion evidence not to emit a profile-derived rule id.'
Assert-Equal $movieEvidence['promotion_rule_source'] 'disabled' 'Expected disabled promotion evidence to identify disabled source.'

$stringFalsePromotionProfile = [pscustomobject]@{
    id = 'string-disabled'
    name = 'String Disabled'
    enabled = $true
    designation = 'movie'
    source_path = 'C:\StringDisabled'
    output_path = 'D:\Processed'
    promotion_enabled = 'false'
    promotion_destination = 'G:\ShouldNotEmit'
    overrides = [pscustomobject]@{}
}
$script:LibraryProfiles = @($script:LibraryProfiles + $stringFalsePromotionProfile)
$stringFalseEvidence = Get-MediaPipelineLibraryProfileEvidenceForPath -SourcePath 'C:\StringDisabled\Movie.mkv'
Assert-Equal $stringFalseEvidence['promotion_enabled'] $false 'Expected string false promotion_enabled to remain disabled in evidence.'
Assert-Equal $stringFalseEvidence['promotion_rule_id'] '' 'Expected string false promotion evidence not to emit a profile-derived rule id.'
Assert-Equal $stringFalseEvidence['promotion_rule_source'] 'disabled' 'Expected string false promotion evidence to identify disabled source.'

$movieOutput = Get-MediaPipelineLibraryOutputRootForPath -SourcePath 'C:\Incoming\Movies\Movie.mkv'
Assert-Equal $movieOutput 'D:\Processed' 'Expected default movie output root to mirror Outsource.'

$runtimeEvidence = New-MediaPipelineRuntimeEffectiveSettingsEvidence -Layers @(
    (New-MediaPipelineRuntimeSettingsLayer -Name 'global' -Source 'active_config' -Keys ([ordered]@{ VideoCodec = 'H264'; AudioMaxChannels = 8; AudioTranscodeCodec = 'eac3'; ConvertVobSubToSrt = $false; VobSubOcrTimeoutSeconds = 1800; OutputContainer = 'mkv'; SizeGuardMode = 'advisory'; EncodeThresholdGB = 8; TVEncodeThresholdGB = 3; MaxEncodeGrowthPercent = 5; CompatibilityEncodeGrowthPercent = 15 })),
    (New-MediaPipelineRuntimeSettingsLayer -Name 'library' -Source 'LibraryProfiles[*].overrides' -Keys ([ordered]@{ VideoCodec = 'HEVC'; OutputContainer = 'mp4'; ConvertVobSubToSrt = $true; VobSubOcrTimeoutSeconds = 900 })),
    (New-MediaPipelineRuntimeSettingsLayer -Name 'show' -Source 'ShowOverrides' -Keys ([ordered]@{ VideoCodec = 'AV1' })),
    (New-MediaPipelineRuntimeSettingsLayer -Name 'folder' -Source 'mediapipeline.folder.json' -Keys ([ordered]@{ VideoCodec = 'H264'; FolderPolicyPath = 'C:\Incoming\Movies\mediapipeline.folder.json' }) -ExcludeKeys @('FolderPolicyPath')),
    (New-MediaPipelineRuntimeSettingsLayer -Name 'file' -Source 'file_overrides.json' -Keys ([ordered]@{ AudioMaxChannels = 2; AudioTranscodeCodec = 'opus' })),
    (New-MediaPipelineRuntimeSettingsLayer -Name 'source' -Source 'ffprobe/probe' -Keys ([ordered]@{ source_codec = 'hevc' }) -SavedConfig:$false)
)
Assert-Equal $runtimeEvidence['schema'] 'runtime_effective_settings.v1' 'Expected runtime evidence schema marker.'
Assert-Equal $runtimeEvidence['library_effective_settings_ref'] 'library-only' 'Expected runtime evidence to reference library-only effective settings.'
Assert-Equal $runtimeEvidence['layers'][0]['name'] 'global' 'Expected global layer first.'
Assert-Equal $runtimeEvidence['layers'][1]['name'] 'library' 'Expected library layer second.'
Assert-Equal $runtimeEvidence['layers'][2]['name'] 'show' 'Expected show layer third.'
Assert-Equal $runtimeEvidence['layers'][3]['name'] 'folder' 'Expected folder layer fourth.'
Assert-Equal $runtimeEvidence['layers'][4]['name'] 'file' 'Expected file layer fifth.'
Assert-Equal $runtimeEvidence['layers'][5]['name'] 'source' 'Expected source layer last.'
Assert-True (-not [bool]$runtimeEvidence['layers'][5]['saved_config']) 'Expected source layer to be diagnostic facts, not saved config.'
Assert-Equal $runtimeEvidence['layers'][3]['keys'].Contains('FolderPolicyPath') $false 'Expected folder metadata keys to be excluded from settings evidence.'
Assert-Equal $runtimeEvidence['effective_values']['VideoCodec']['value'] 'H264' 'Expected final VideoCodec evidence from folder layer.'
Assert-Equal $runtimeEvidence['effective_values']['VideoCodec']['source_layer'] 'folder' 'Expected final VideoCodec source layer to be folder.'
Assert-Contains $runtimeEvidence['effective_values']['VideoCodec']['overrode'] 'global' 'Expected VideoCodec provenance to include overridden global layer.'
Assert-Contains $runtimeEvidence['effective_values']['VideoCodec']['overrode'] 'library' 'Expected VideoCodec provenance to include overridden library layer.'
Assert-Contains $runtimeEvidence['effective_values']['VideoCodec']['overrode'] 'show' 'Expected VideoCodec provenance to include overridden show layer.'
Assert-Equal $runtimeEvidence['effective_values']['AudioMaxChannels']['source_layer'] 'file' 'Expected file override layer to win for AudioMaxChannels evidence.'
Assert-Equal $runtimeEvidence['effective_values']['OutputContainer']['source_layer'] 'library' 'Expected OutputContainer path evidence fixture to remain library/global scoped.'
Assert-Equal $runtimeEvidence['effective_values']['ConvertVobSubToSrt']['value'] $true 'Expected VobSub conversion to remain present in runtime effective evidence.'
Assert-Equal $runtimeEvidence['effective_values']['ConvertVobSubToSrt']['source_layer'] 'library' 'Expected VobSub conversion evidence to report library source layer.'
Assert-True (-not $runtimeEvidence['effective_values'].Contains('FolderPolicyPath')) 'Expected runtime effective settings to exclude folder metadata keys from effective values.'
Assert-True (-not $runtimeEvidence.Contains('library_effective_settings')) 'Expected runtime evidence not to redefine library_effective_settings.'
$routingSources = Get-MediaPipelineRuntimeEffectiveSettingSources -RuntimeEffectiveSettings $runtimeEvidence -Keys @('VideoCodec','AudioMaxChannels')
Assert-Equal $routingSources['VideoCodec']['source_layer'] 'folder' 'Expected routing source map to identify winning folder layer.'
Assert-Equal $routingSources['AudioMaxChannels']['source_layer'] 'file' 'Expected routing source map to identify winning file layer.'
$runtimeLayers = Get-MediaPipelineRuntimeLayerNames -RuntimeEffectiveSettings $runtimeEvidence
Assert-Equal ($runtimeLayers -join '>') 'global>library>show>folder>file>source' 'Expected runtime layer summary order to match precedence order.'
$secretLikeRuntimeKeys = @($runtimeEvidence['effective_values'].Keys | Where-Object { [string]$_ -match '(?i)(password|token|secret|auth)' })
Assert-Equal @($secretLikeRuntimeKeys).Count 0 'Expected runtime evidence fixture not to expose auth-like config keys.'

$precedenceEvidence = New-MediaPipelineRuntimeEffectiveSettingsEvidence -Layers @(
    (New-MediaPipelineRuntimeSettingsLayer -Name 'global' -Source 'active_config' -Keys ([ordered]@{ DropAssAfterConversion = $false; RoutingProfile = 'plex_direct_stream'; AudioMaxChannels = 8 })),
    (New-MediaPipelineRuntimeSettingsLayer -Name 'library' -Source 'LibraryProfiles[*].overrides' -Keys ([ordered]@{ DropAssAfterConversion = $true; RoutingProfile = 'manual'; AudioMaxChannels = 6 })),
    (New-MediaPipelineRuntimeSettingsLayer -Name 'show' -Source 'ShowOverrides' -Keys ([ordered]@{ DropAssAfterConversion = $false })),
    (New-MediaPipelineRuntimeSettingsLayer -Name 'folder' -Source 'mediapipeline.folder.json' -Keys ([ordered]@{ RoutingProfile = 'archive_quality'; AudioMaxChannels = 4 })),
    (New-MediaPipelineRuntimeSettingsLayer -Name 'file' -Source 'file_overrides.json' -Keys ([ordered]@{ AudioMaxChannels = 2 }))
)
Assert-Equal $precedenceEvidence['effective_values']['DropAssAfterConversion']['source_layer'] 'show' 'Expected show override layer to beat global/library for supported subtitle cleanup keys.'
Assert-Contains $precedenceEvidence['effective_values']['DropAssAfterConversion']['overrode'] 'global' 'Expected show subtitle cleanup evidence to record overridden global layer.'
Assert-Contains $precedenceEvidence['effective_values']['DropAssAfterConversion']['overrode'] 'library' 'Expected show subtitle cleanup evidence to record overridden library layer.'
Assert-Equal $precedenceEvidence['effective_values']['RoutingProfile']['source_layer'] 'folder' 'Expected folder policy layer to beat global/library for supported routing keys.'
Assert-Contains $precedenceEvidence['effective_values']['RoutingProfile']['overrode'] 'global' 'Expected folder routing evidence to record overridden global layer.'
Assert-Contains $precedenceEvidence['effective_values']['RoutingProfile']['overrode'] 'library' 'Expected folder routing evidence to record overridden library layer.'
Assert-Equal $precedenceEvidence['effective_values']['AudioMaxChannels']['source_layer'] 'file' 'Expected per-file layer to beat global/library/folder for supported audio keys.'
Assert-Contains $precedenceEvidence['effective_values']['AudioMaxChannels']['overrode'] 'global' 'Expected per-file audio evidence to record overridden global layer.'
Assert-Contains $precedenceEvidence['effective_values']['AudioMaxChannels']['overrode'] 'library' 'Expected per-file audio evidence to record overridden library layer.'
Assert-Contains $precedenceEvidence['effective_values']['AudioMaxChannels']['overrode'] 'folder' 'Expected per-file audio evidence to record overridden folder layer.'

$unsupportedEvidence = New-MediaPipelineRuntimeEffectiveSettingsEvidence `
    -Layers @((New-MediaPipelineRuntimeSettingsLayer -Name 'global' -Source 'active_config' -Keys ([ordered]@{ RoutingProfile = 'plex_direct_stream' }))) `
    -UnsupportedKeys @('ProcessingStrategy', 'OutputSizeCheck') `
    -IgnoredKeys @('FolderPolicyPath', 'UnknownFileOverride') `
    -Warnings @('unsupported runtime keys ignored')
Assert-Contains $unsupportedEvidence['unsupported_keys'] 'ProcessingStrategy' 'Expected friendly label key to be reported as unsupported evidence, not applied.'
Assert-Contains $unsupportedEvidence['unsupported_keys'] 'OutputSizeCheck' 'Expected friendly output-size label key to be reported as unsupported evidence, not applied.'
Assert-Contains $unsupportedEvidence['ignored_keys'] 'FolderPolicyPath' 'Expected folder policy metadata key to be reported as ignored evidence.'
Assert-True (-not $unsupportedEvidence['effective_values'].Contains('ProcessingStrategy')) 'Expected unsupported friendly label key not to appear as an effective runtime setting.'
Assert-True (-not $unsupportedEvidence['effective_values'].Contains('OutputSizeCheck')) 'Expected unsupported friendly output label key not to appear as an effective runtime setting.'

$jobAEvidence = New-MediaPipelineRuntimeEffectiveSettingsEvidence `
    -Layers @((New-MediaPipelineRuntimeSettingsLayer -Name 'global' -Source 'active_config' -Keys ([ordered]@{ RoutingProfile = 'manual' }))) `
    -UnsupportedKeys @('JobAUnsupported')
$jobBEvidence = New-MediaPipelineRuntimeEffectiveSettingsEvidence `
    -Layers @((New-MediaPipelineRuntimeSettingsLayer -Name 'global' -Source 'active_config' -Keys ([ordered]@{ RoutingProfile = 'plex_direct_stream' })))
Assert-Contains $jobAEvidence['unsupported_keys'] 'JobAUnsupported' 'Expected job A unsupported-key evidence fixture.'
Assert-True (-not (@($jobBEvidence['unsupported_keys']) -contains 'JobAUnsupported')) 'Expected job B runtime evidence not to inherit job A unsupported keys.'
Assert-True (-not $jobBEvidence['effective_values'].Contains('JobAUnsupported')) 'Expected job B runtime effective values not to inherit job A unsupported key.'

$routingConsumer = New-MediaPipelineRuntimeConsumerSettingsEvidence -RuntimeEffectiveSettings $runtimeEvidence -Consumer 'routing' -Keys (Get-MediaPipelineRuntimeRoutingConsumerKeys) -DecisionScope 'copy_remux_encode' -ActionSelected 'remux' -DecisionImpact ([ordered]@{ SizeGuardMode = 'post_encode_size_guard' })
Assert-Equal $routingConsumer['schema'] 'runtime_consumer_settings.v1' 'Expected consumer settings evidence schema marker.'
Assert-True ([bool]$routingConsumer['diagnostic_only']) 'Expected consumer settings evidence to be diagnostic-only.'
Assert-Equal $routingConsumer['settings']['VideoCodec']['source_layer'] 'folder' 'Expected routing consumer evidence to report final VideoCodec layer.'
Assert-Equal $routingConsumer['settings']['OutputContainer']['source_layer'] 'library' 'Expected routing consumer evidence to report OutputContainer layer without adding folder/file support.'
Assert-Equal $routingConsumer['settings']['SizeGuardMode']['decision_impact'] 'post_encode_size_guard' 'Expected routing consumer evidence to distinguish size guard impact.'

$audioConsumer = New-MediaPipelineRuntimeConsumerSettingsEvidence -RuntimeEffectiveSettings $runtimeEvidence -Consumer 'audio' -Keys (Get-MediaPipelineRuntimeAudioConsumerKeys) -DecisionScope 'audio_policy' -ActionEvidence 'audio action is selected when the audio consumer builds ffmpeg args'
Assert-Equal $audioConsumer['settings']['AudioTranscodeCodec']['value'] 'opus' 'Expected audio consumer evidence to report final transcode codec value.'
Assert-Equal $audioConsumer['settings']['AudioTranscodeCodec']['source_layer'] 'file' 'Expected audio consumer evidence to report file layer for transcode codec.'
Assert-Equal $audioConsumer['settings']['AudioMaxChannels']['source_layer'] 'file' 'Expected audio consumer evidence to report file layer for max channels.'

$subtitleConsumer = New-MediaPipelineRuntimeConsumerSettingsEvidence -RuntimeEffectiveSettings $runtimeEvidence -Consumer 'subtitles' -Keys (Get-MediaPipelineRuntimeSubtitleConsumerKeys) -DecisionScope 'subtitle_policy' -ActionEvidence 'subtitle actions are selected when subtitle streams are filtered and converted'
Assert-Equal $subtitleConsumer['settings']['ConvertVobSubToSrt']['value'] $true 'Expected subtitle consumer evidence to report VobSub conversion value.'
Assert-Equal $subtitleConsumer['settings']['ConvertVobSubToSrt']['source_layer'] 'library' 'Expected subtitle consumer evidence to report VobSub conversion source layer.'
Assert-Equal $subtitleConsumer['settings']['VobSubOcrTimeoutSeconds']['source_layer'] 'library' 'Expected subtitle consumer evidence to report VobSub OCR timeout source layer.'
Assert-True ($subtitleConsumer['settings'].Contains('TreatVobSubSignsSongsAsForced')) 'Expected subtitle consumer evidence to include VobSub signs/songs key even when unresolved.'

$containerPlanning = Get-MediaPipelineOutputContainerPlanningEvidence -LibraryOverrides ([ordered]@{ OutputContainer = 'mp4' }) -LibraryOutputRoot 'D:\Processed' -LibrarySourceRoot 'C:\Incoming\Movies' -DefaultOutputContainer 'mkv'
Assert-Equal $containerPlanning['consumer'] 'container_path_planning' 'Expected container/path consumer evidence.'
Assert-Equal $containerPlanning['settings']['OutputContainer']['value'] 'mp4' 'Expected container path evidence to report planned OutputContainer.'
Assert-Equal $containerPlanning['settings']['OutputContainer']['source_layer'] 'library' 'Expected container path evidence to report library source layer.'
Assert-Equal $containerPlanning['planned_output_root'] 'D:\Processed' 'Expected container path evidence to report planned output root.'
Assert-Equal $containerPlanning['planned_output_path_available'] $false 'Expected container path evidence not to claim final path before Get-OutputPaths emits it.'
Assert-Equal $containerPlanning['folder_file_output_container_override_supported'] $false 'Expected container path evidence not to claim folder/file OutputContainer support.'
Assert-True ($containerPlanning['warning'] -match 'global/library') 'Expected container path evidence to warn when only global/library container evidence is active.'

$fileContainerRuntimeEvidence = New-MediaPipelineRuntimeEffectiveSettingsEvidence -Layers @(
    (New-MediaPipelineRuntimeSettingsLayer -Name 'global' -Source 'active_config' -Keys ([ordered]@{ OutputContainer = 'mkv' })),
    (New-MediaPipelineRuntimeSettingsLayer -Name 'file' -Source 'file_overrides.json' -Keys ([ordered]@{ OutputContainer = 'mp4' }))
)
$fileContainerPlanning = Get-MediaPipelineOutputContainerPlanningEvidence -LibraryOverrides ([ordered]@{}) -RuntimeEffectiveSettings $fileContainerRuntimeEvidence -LibraryOutputRoot 'D:\Processed' -LibrarySourceRoot 'C:\Incoming\Movies' -DefaultOutputContainer 'mkv'
Assert-Equal $fileContainerPlanning['settings']['OutputContainer']['value'] 'mp4' 'Expected file OutputContainer evidence to win when runtime evidence is supplied.'
Assert-Equal $fileContainerPlanning['settings']['OutputContainer']['source_layer'] 'file' 'Expected file OutputContainer evidence to report file source layer.'
Assert-Equal $fileContainerPlanning['folder_file_output_container_override_supported'] $true 'Expected container path evidence to report runtime file OutputContainer support.'

$sizeGuardMetadata = [pscustomobject]@{
    mode = 'advisory'
    routing_profile = 'plex_direct_stream'
    route_reason_code = 'bitrate_over_threshold'
    max_growth_percent = 15.0
    limit_ratio = 1.15
    source_size_bytes = 100L
    output_size_bytes = 125L
    ratio = 1.25
    exceeded = $true
    enforced = $false
    message = 'encoded output exceeds advisory growth policy'
}
$sizeGuardRoutePlan = [pscustomobject]@{
    IsTV = $false
    ThresholdGB = 8.0
    EstimatedBitrateMbps = 42.0
    BitrateThresholdMbps = 35.0
}
$sizeGuardEvidence = New-MediaPipelineSizeGuardEvidence -RuntimeEffectiveSettings $runtimeEvidence -SizePolicyResult $sizeGuardMetadata -RoutePlan $sizeGuardRoutePlan
Assert-Equal $sizeGuardEvidence['schema'] 'size_guard_evidence.v1' 'Expected size guard evidence schema marker.'
Assert-True ([bool]$sizeGuardEvidence['diagnostic_only']) 'Expected size guard evidence to be diagnostic-only.'
Assert-Equal $sizeGuardEvidence['outcome'] 'warn' 'Expected advisory exceeded size guard to emit warning evidence without blocking.'
Assert-Equal $sizeGuardEvidence['strictness'] 'advisory' 'Expected advisory size guard strictness.'
Assert-Equal $sizeGuardEvidence['target_size_key'] 'EncodeThresholdGB' 'Expected movie size guard evidence to identify movie GB target key.'
Assert-Equal $sizeGuardEvidence['target_size_gb'] 8 'Expected size guard evidence to expose GB target setting separately from Mbps gate.'
Assert-Equal $sizeGuardEvidence['bitrate_gate_mbps'] 35.0 'Expected size guard evidence to expose the routing Mbps gate as distinct evidence.'
Assert-Equal $sizeGuardEvidence['settings']['settings']['SizeGuardMode']['source_layer'] 'global' 'Expected size guard evidence to include source layer for SizeGuardMode.'
Assert-True ($sizeGuardEvidence['distinction_note'] -match 'GB target settings' -and $sizeGuardEvidence['distinction_note'] -match 'Mbps values are routing bitrate gates') 'Expected size guard evidence to distinguish GB targets from Mbps gates.'

$strictSizeGuardEvidence = New-MediaPipelineSizeGuardEvidence -RuntimeEffectiveSettings $runtimeEvidence -SizePolicyResult ([pscustomobject]@{
    mode = 'strict'
    exceeded = $true
    enforced = $true
    source_size_bytes = 100L
    output_size_bytes = 130L
    max_growth_percent = 5.0
    limit_ratio = 1.05
    ratio = 1.30
    message = 'encoded output exceeds strict growth policy'
}) -RoutePlan $sizeGuardRoutePlan
Assert-Equal $strictSizeGuardEvidence['outcome'] 'block' 'Expected strict exceeded size guard to emit block evidence.'
Assert-Equal $strictSizeGuardEvidence['strictness'] 'hard' 'Expected strict size guard to be classified as a hard rule.'

$publishEvidence = New-MediaPipelinePublishEvidence -PublishResult ([pscustomobject]@{
    Ok = $true
    PublishState = 'pending_publish'
    PublishMode = 'output-space-deferred'
    OutputPath = 'D:\Processed\Movie.mkv'
    OutputSizeBytes = 125L
    Reason = ''
    ParkedForOutputSpace = $true
}) -Route 'encode'
Assert-Equal $publishEvidence['schema'] 'publish_evidence.v1' 'Expected publish evidence schema marker.'
Assert-True ([bool]$publishEvidence['attempted']) 'Expected publish evidence to report an attempted publish result.'
Assert-True ([bool]$publishEvidence['allowed']) 'Expected pending publish parking success to remain allowed evidence.'
Assert-True ([bool]$publishEvidence['deferred']) 'Expected output-space pending publish evidence to mark deferred status.'
Assert-Equal $publishEvidence['outcome'] 'deferred' 'Expected pending publish evidence outcome.'

$verificationEvidence = New-MediaPipelineVerificationEvidence -SizeGuardEvidence $sizeGuardEvidence -PublishEvidence $publishEvidence
Assert-Equal $verificationEvidence['schema'] 'verification_evidence.v1' 'Expected verification evidence schema marker.'
Assert-Contains $verificationEvidence['checks_run'] 'size_guard' 'Expected verification evidence to include size guard check.'
Assert-Contains $verificationEvidence['checks_run'] 'publish_result' 'Expected verification evidence to include publish result check.'
Assert-Contains $verificationEvidence['warnings'] 'size_guard_warning' 'Expected advisory size guard evidence to surface as a warning.'
Assert-Contains $verificationEvidence['warnings'] 'publish_deferred_pending_drain' 'Expected deferred publish evidence to surface as a pending-drain warning.'
Assert-Equal $verificationEvidence['result'] 'warning' 'Expected warning-only verification evidence not to become a blocking failure.'

$fileConfigMap = ConvertTo-MediaPipelineFileOverrideConfigMap -Override ([pscustomobject]@{
    audio = [pscustomobject]@{
        maxChannels = 2
        downmixMode = 'stereo'
        preferDefaultLanguage = 'eng'
    }
})
Assert-Equal $fileConfigMap['AudioMaxChannels'] 2 'Expected file override evidence to include promoted max channel config key.'
Assert-Equal $fileConfigMap['AudioDownmixMode'] 'stereo' 'Expected file override evidence to include promoted downmix config key.'
Assert-Equal @($fileConfigMap['PreferredDefaultAudioLanguages'])[0] 'eng' 'Expected file override evidence to include promoted preferred language config key.'
$routeVideoConfigMap = ConvertTo-MediaPipelineFileOverrideConfigMap -Override ([pscustomobject]@{
    routing = [pscustomobject]@{
        profile = 'transcode'
        routeThresholdMode = 'bitrate'
    }
    video = [pscustomobject]@{
        codec = 'h264_nvenc'
        container = 'mp4'
        encodePreset = 'balanced_nvenc'
        encodeLadder = 'plex_compat'
    }
})
Assert-Equal $routeVideoConfigMap['RouteForce'] 'encode' 'Expected routing.profile transcode to force encode route.'
Assert-Equal $routeVideoConfigMap['RouteThresholdMode'] 'bitrate' 'Expected route threshold mode to be promoted.'
Assert-Equal $routeVideoConfigMap['VideoCodec'] 'h264_nvenc' 'Expected file override video codec to be promoted.'
Assert-Equal $routeVideoConfigMap['OutputContainer'] 'mp4' 'Expected file override output container to be promoted.'
Assert-Equal $routeVideoConfigMap['EncodeTuningPreset'] 'balanced_nvenc' 'Expected file override encode preset to be promoted.'
Assert-Equal $routeVideoConfigMap['EncodeLadder'] 'plex_compat' 'Expected file override encode ladder to be promoted.'
$folderRouteConfigMap = ConvertTo-MediaPipelineFileOverrideConfigMap -Override ([pscustomobject]@{
    routing = [pscustomobject]@{ profile = 'remux' }
})
Assert-Equal $folderRouteConfigMap['RouteForce'] 'remux' 'Expected routing.profile remux to force remux route.'
Assert-Throws -ScriptBlock {
    ConvertTo-MediaPipelineFileOverrideConfigMap -Override ([pscustomobject]@{
        routing = [pscustomobject]@{ profile = 'raw;bad' }
    }) | Out-Null
} -Message 'Expected invalid routing.profile to fail before processing.' -ExpectedText "Invalid file override value for 'routing.profile'"
Assert-Throws -ScriptBlock {
    ConvertTo-MediaPipelineFileOverrideConfigMap -Override ([pscustomobject]@{
        routing = [pscustomobject]@{ profile = 'remux' }
        video = [pscustomobject]@{ codec = 'h264_nvenc' }
    }) | Out-Null
} -Message 'Expected remux plus encode-only video settings to fail safely.' -ExpectedText 'routing.profile=remux cannot be combined'

$audioExactOverride = [pscustomobject]@{
    keepTracks = @([pscustomobject]@{ streamIndex = 2; language = 'eng'; codec = 'truehd'; channels = 8 })
}
Assert-True (-not (Test-AudioTrackKeptByOverride -Language 'eng' -Channels 6 -Title 'English 5.1' -Codec 'ac3' -StreamIndex 1 -AudioOverride $audioExactOverride)) 'Expected exact audio keep selector to drop a non-selected duplicate-language stream.'
Assert-True (Test-AudioTrackKeptByOverride -Language 'eng' -Channels 8 -Title 'English Atmos' -Codec 'truehd' -StreamIndex 2 -AudioOverride $audioExactOverride) 'Expected exact audio keep selector to keep the matching stream.'
Assert-True (-not (Test-AudioTrackKeptByOverride -Language 'eng' -Channels 8 -Title 'English Atmos' -Codec 'truehd' -StreamIndex 3 -AudioOverride $audioExactOverride)) 'Expected exact audio keep selector to require the selected stream index.'

$audioAliasOverride = [pscustomobject]@{
    keepTracks = @([pscustomobject]@{ language = 'eng' })
}
Assert-True (Test-AudioTrackKeptByOverride -Language 'en' -Channels 6 -Title 'English 5.1' -Codec 'ac3' -StreamIndex 1 -AudioOverride $audioAliasOverride) 'Expected audio keep selector to normalize source language aliases.'
Assert-True (Test-AudioTrackKeptByOverride -Language 'english' -Channels 2 -Title 'English Commentary' -Codec 'ac3' -StreamIndex 2 -AudioOverride $audioAliasOverride) 'Expected audio keep selector to normalize source language names.'

$audioExactDropOverride = [pscustomobject]@{
    dropTracks = @([pscustomobject]@{ streamIndex = 2; language = 'eng'; codec = 'ac3'; channels = 2 })
}
Assert-True (-not (Test-AudioTrackKeptByOverride -Language 'eng' -Channels 2 -Title 'English Commentary' -Codec 'ac3' -StreamIndex 2 -AudioOverride $audioExactDropOverride)) 'Expected exact audio drop selector to drop only the matching stream.'
Assert-True (Test-AudioTrackKeptByOverride -Language 'eng' -Channels 6 -Title 'English 5.1' -Codec 'ac3' -StreamIndex 1 -AudioOverride $audioExactDropOverride) 'Expected exact audio drop selector to keep non-selected streams.'

$audioAliasDropOverride = [pscustomobject]@{
    dropTracks = @([pscustomobject]@{ language = 'jpn' })
}
Assert-True (-not (Test-AudioTrackKeptByOverride -Language 'japanese' -Channels 2 -Title 'Japanese' -Codec 'aac' -StreamIndex 5 -AudioOverride $audioAliasDropOverride)) 'Expected audio drop selector to normalize source language names.'

$subtitleExactOverride = [pscustomobject]@{
    keepTracks = @([pscustomobject]@{ streamIndex = 3; language = 'eng'; codec = 'subrip'; forced = $true })
}
Assert-True (Test-SubtitleTrackKeptByOverride -Language 'eng' -IsForced:$true -Title 'English Forced' -Codec 'subrip' -StreamIndex 3 -SubtitleOverride $subtitleExactOverride) 'Expected exact subtitle keep selector to keep the matching stream.'
Assert-True (-not (Test-SubtitleTrackKeptByOverride -Language 'eng' -IsForced:$false -Title 'English SDH' -Codec 'subrip' -StreamIndex 4 -SubtitleOverride $subtitleExactOverride)) 'Expected exact subtitle keep selector to drop a non-selected duplicate-language stream.'

$subtitleAliasOverride = [pscustomobject]@{
    keepTracks = @([pscustomobject]@{ language = 'eng'; forced = $false })
}
Assert-True (Test-SubtitleTrackKeptByOverride -Language 'english' -IsForced:$false -Title 'English SDH' -Codec 'subrip' -StreamIndex 4 -SubtitleOverride $subtitleAliasOverride) 'Expected subtitle keep selector to normalize source language names.'

$audioAliasRenameOverride = [pscustomobject]@{
    renameTracks = @([pscustomobject]@{ language = 'eng'; channels = 2; newTitle = 'English Commentary' })
}
Assert-Equal (Get-AudioTrackTitleOverride -Language 'english' -Channels 2 -AudioOverride $audioAliasRenameOverride) 'English Commentary' 'Expected audio title override to normalize source language names.'

$subtitleAliasRenameOverride = [pscustomobject]@{
    renameTracks = @([pscustomobject]@{ language = 'eng'; forced = $true; newTitle = 'English Forced' })
}
Assert-Equal (Get-SubtitleTrackTitleOverride -Language 'en' -IsForced:$true -SubtitleOverride $subtitleAliasRenameOverride) 'English Forced' 'Expected subtitle title override to normalize source language aliases.'

Assert-FileOverrideExactTrackSelectorsResolvable `
    -TrackKind 'audio' `
    -Tracks @([pscustomobject]@{
        index = 7
        codec_type = 'audio'
        codec_name = 'ac3'
        channels = 6
        tags = [pscustomobject]@{ language = 'en'; title = 'English 5.1' }
        disposition = [pscustomobject]@{ forced = 0 }
    }) `
    -OverrideSection ([pscustomobject]@{ keepTracks = @([pscustomobject]@{ streamIndex = 7; language = 'eng'; codec = 'ac3'; channels = 6 }) })

Assert-Throws -ScriptBlock {
    Assert-FileOverrideExactTrackSelectorsResolvable `
        -TrackKind 'audio' `
        -Tracks @([pscustomobject]@{
            index = 1
            codec_name = 'ac3'
            channels = 6
            tags = [pscustomobject]@{ language = 'eng'; title = 'English 5.1' }
            disposition = [pscustomobject]@{ forced = 0 }
        }) `
        -OverrideSection ([pscustomobject]@{ keepTracks = @([pscustomobject]@{ streamIndex = 2; language = 'eng' }) })
} -Message 'Expected missing exact audio selector to fail safely during processing.' -ExpectedText 'FILE_OVERRIDE_EXACT_TRACK_UNAVAILABLE'
Assert-Throws -ScriptBlock {
    Assert-FileOverrideExactTrackSelectorsResolvable `
        -TrackKind 'subtitle' `
        -Tracks @(
            [pscustomobject]@{
                index = 3
                codec_type = 'audio'
                codec_name = 'ac3'
                channels = 6
                tags = [pscustomobject]@{ language = 'eng'; title = 'English 5.1' }
                disposition = [pscustomobject]@{ forced = 0 }
            },
            [pscustomobject]@{
                index = 4
                codec_type = 'subtitle'
                codec_name = 'subrip'
                tags = [pscustomobject]@{ language = 'eng'; title = 'English SDH' }
                disposition = [pscustomobject]@{ forced = 0 }
            }
        ) `
        -OverrideSection ([pscustomobject]@{ keepTracks = @([pscustomobject]@{ streamIndex = 3; language = 'eng' }) })
} -Message 'Expected exact subtitle selector not to match an audio stream with the same index.' -ExpectedText 'FILE_OVERRIDE_EXACT_TRACK_UNAVAILABLE'

$overrideTempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-file-override-stage5d-" + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $overrideTempRoot -Force | Out-Null
    $manifestPath = Join-Path $overrideTempRoot 'file_overrides.json'
    $manifest = [ordered]@{
        version = 1
        entries = [ordered]@{
            'c:/incoming/movies' = [ordered]@{
                routing = [ordered]@{ profile = 'remux' }
            }
            'c:/incoming/movies/show' = [ordered]@{
                routing = [ordered]@{ profile = 'transcode'; routeThresholdMode = 'bitrate' }
                video = [ordered]@{ codec = 'h264_nvenc'; container = 'mp4'; encodePreset = 'balanced_nvenc'; encodeLadder = 'plex_compat' }
            }
            'c:/incoming/movies/show/movie.mkv' = [ordered]@{
                routing = [ordered]@{ profile = 'remux' }
            }
        }
    }
    $manifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    $script:LocalStateLayout = [pscustomobject]@{ Paths = [pscustomobject]@{ FileOverrides = $manifestPath } }
    $script:CapturedLogs.Clear()
    $folderMatch = Resolve-FileOverrideMatch -SourcePath 'C:\Incoming\Movies\Show\Other.mkv'
    Assert-Equal $folderMatch.Scope 'folder' 'Expected deepest folder override match for covered source.'
    Assert-Equal $folderMatch.MatchedPath 'c:/incoming/movies/show' 'Expected deepest folder override path to win.'
    $exactMatch = Resolve-FileOverrideMatch -SourcePath 'C:\Incoming\Movies\Show\Movie.mkv'
    Assert-Equal $exactMatch.Scope 'file' 'Expected exact file override to beat folder override.'
    $script:ActiveOverrides = [ordered]@{ RoutingProfile = 'manual' }
    Merge-FileOverrideIntoActiveOverrides -SourcePath 'C:\Incoming\Movies\Show\Other.mkv'
    Assert-Equal $script:ActiveOverrides['RouteForce'] 'encode' 'Expected folder route/video override to force encode through active overrides.'
    Assert-Equal $script:ActiveOverrides['VideoCodec'] 'h264_nvenc' 'Expected folder video codec override to be active.'
    Assert-Equal $script:ActiveOverrides['OutputContainer'] 'mp4' 'Expected folder container override to be active.'
    Assert-Equal $script:LastFileOverrideMatch.Scope 'folder' 'Expected merge metadata to preserve folder scope.'
    Assert-True (@($script:CapturedLogs | Where-Object { $_.Message -match 'applied route/video override' -and $_.Message -match 'fields=routing.profile, routing.routeThresholdMode, video.codec, video.container, video.encodePreset, video.encodeLadder' }).Count -gt 0) 'Expected route/video override application log.'
    Assert-True (@($script:CapturedLogs | Where-Object { $_.Level -eq 'WARN' -and $_.Message -match 'forces transcode' }).Count -gt 0) 'Expected transcode-forcing file override warning log.'
} finally {
    Remove-Item -LiteralPath $overrideTempRoot -Recurse -Force -ErrorAction SilentlyContinue
    $script:CachedFileOverridesManifest = $null
    $script:ActiveOverrides = $null
    $script:LastFileOverrideConfigMap = $null
    $script:LastFileOverrideMatch = $null
}
$fileUnknownConfigMap = ConvertTo-MediaPipelineFileOverrideConfigMap -Override ([pscustomobject]@{
    audio = [pscustomobject]@{
        maxChannels = 4
        ProcessingStrategy = 'manual'
    }
    video = [pscustomobject]@{
        VideoCodec = 'AV1'
    }
})
Assert-Equal $fileUnknownConfigMap['AudioMaxChannels'] 4 'Expected supported per-file audio key to be promoted.'
Assert-True (-not $fileUnknownConfigMap.Contains('ProcessingStrategy')) 'Expected friendly label key in per-file override payload not to be promoted.'
Assert-True (-not $fileUnknownConfigMap.Contains('VideoCodec')) 'Expected unsupported legacy-cased per-file video override key not to be promoted.'

$pipelineProcessingText = Get-Content -LiteralPath (Join-Path $repoRoot 'engine\process\pipeline_processing.ps1') -Raw
$routingText = Get-Content -LiteralPath (Join-Path $repoRoot 'engine\decide\routing.ps1') -Raw
$outputPathText = Get-Content -LiteralPath (Join-Path $repoRoot 'engine\paths\output_path_planning.ps1') -Raw
Assert-True ($pipelineProcessingText -match 'New-MediaPipelineRuntimeEffectiveSettingsEvidence' -and $pipelineProcessingText -match 'runtime_effective_settings\s*=\s*\$runtimeEffectiveSettings') 'Expected route event data to include diagnostic-only runtime effective settings evidence.'
Assert-True ($pipelineProcessingText -match 'library_effective_settings_ref\s*=\s*''library-only''' -and $pipelineProcessingText -match 'runtime_effective_settings_available\s*=\s*\$false') 'Expected job_started evidence to label library effective settings as library-only and avoid fake final runtime settings.'
Assert-True ($pipelineProcessingText -match "EventType 'job_started'" -and $pipelineProcessingText -match 'promotion_enabled\s*=\s*\[bool\]\$libraryEvidenceForJob\[''promotion_enabled''\]' -and $pipelineProcessingText -match 'promotion_destination_root\s*=\s*\[string\]\$libraryEvidenceForJob\[''promotion_destination_root''\]' -and $pipelineProcessingText -match 'promotion_rule_id\s*=\s*\[string\]\$libraryEvidenceForJob\[''promotion_rule_id''\]' -and $pipelineProcessingText -match 'promotion_rule_source\s*=\s*\[string\]\$libraryEvidenceForJob\[''promotion_rule_source''\]') 'Expected job_started evidence to include promotion state, destination, rule id, and rule source from library evidence.'
Assert-True ($pipelineProcessingText -match "EventType 'route_selected'" -and $pipelineProcessingText -match 'route\s*=\s*\$routePlan\.Route' -and $pipelineProcessingText -match 'reason_code\s*=\s*\$routePlan\.ReasonCode' -and $pipelineProcessingText -match 'reason\s*=\s*\$routePlan\.Reason') 'Expected route_selected event to preserve final route decision and reason fields.'
Assert-True ($pipelineProcessingText -match '(?s)EventType ''route_selected''.*promotion_enabled\s*=.*promotion_destination_root\s*=.*promotion_rule_id\s*=.*promotion_rule_source\s*=') 'Expected route_selected evidence to include promotion state, destination, rule id, and rule source from library evidence.'
Assert-True ($pipelineProcessingText -match 'PROMOTION: enabled destination=' -and $pipelineProcessingText -match 'rule=\$\(\$libraryEvidenceForJob\[''promotion_rule_id''\]\)' -and $pipelineProcessingText -match 'source=\$\(\$libraryEvidenceForJob\[''promotion_rule_source''\]\)') 'Expected concise promotion log line for enabled profile-derived promotion evidence.'
Assert-True (-not ($pipelineProcessingText -match 'PROMOTION: disabled.*destination=')) 'Expected disabled promotion logging not to emit a misleading destination.'
Assert-True ($pipelineProcessingText -match 'routing_key_sources\s*=\s*\$routingKeySources' -and $pipelineProcessingText -match '\$routeRuleOutcomes\s*=\s*Get-MediaRouteRuleOutcomeEvidence' -and $pipelineProcessingText -match 'route_rule_outcomes\s*=\s*\$routeRuleOutcomes') 'Expected route_selected evidence to expose routing key sources and rule outcomes.'
Assert-True ($pipelineProcessingText -match 'runtime_consumer_evidence\s*=\s*\$runtimeConsumerEvidence' -and $pipelineProcessingText -match 'audio_consumer_settings\s*=\s*\$audioConsumerSettings' -and $pipelineProcessingText -match 'subtitle_consumer_settings\s*=\s*\$subtitleConsumerSettings') 'Expected route_selected evidence to expose consumer-specific runtime settings.'
Assert-True ($pipelineProcessingText -match 'container_path_planning_evidence\s*=\s*\$containerPathPlanningEvidence') 'Expected route_selected evidence to expose container/path planning evidence.'
Assert-True ($pipelineProcessingText -match 'size_guard_evidence\s*=\s*\$Result\.SizeGuardEvidence' -and $pipelineProcessingText -match 'verification_evidence\s*=\s*\$Result\.VerificationEvidence' -and $pipelineProcessingText -match 'publish_evidence\s*=\s*\$Result\.PublishEvidence') 'Expected job_completed evidence to expose size guard, verification, and publish diagnostics.'
Assert-True ($pipelineProcessingText -match 'RUNTIME EVIDENCE: layers=') 'Expected concise runtime evidence debug logging.'
Assert-True ($pipelineProcessingText -match 'Pop-MediaPipelineActiveConfigOverrides' -and $pipelineProcessingText -match '\$script:ActiveOverrides\s*=\s*\$null' -and $pipelineProcessingText -match '\$script:LastFileOverrideConfigMap\s*=\s*\$null') 'Expected processing finally block to restore/clear active override state.'
Assert-True ($pipelineProcessingText -match '\$script:CurrentRuntimeEffectiveSettings\s*=\s*\$null' -and $pipelineProcessingText -match '\$script:CurrentRoutePlan\s*=\s*\$null' -and $pipelineProcessingText -match '\$script:CurrentSizePolicyResult\s*=\s*\$null') 'Expected processing finally block to clear runtime evidence, route, and size guard state.'
Assert-True ($pipelineProcessingText -match '\$script:LastPublishResult\s*=\s*\$null' -and $pipelineProcessingText -match '\$script:CurrentRouteReasonCode\s*=\s*\$null' -and $pipelineProcessingText -match '\$script:CurrentRouteReason\s*=\s*\$null') 'Expected processing finally block to clear publish and route reason state between jobs.'
Assert-True ($routingText -match 'function Get-MediaRouteRuleOutcomeEvidence' -and $routingText -match 'runtime_effective_settings_ref' -and $routingText -match 'library_effective_settings_ref') 'Expected route metadata helper to expose runtime provenance and library-only references.'
Assert-True ($outputPathText -match 'function New-MediaPipelineRuntimeConsumerSettingsEvidence' -and $outputPathText -match 'function Get-MediaPipelineOutputContainerPlanningEvidence' -and $outputPathText -match 'function New-MediaPipelineSizeGuardEvidence' -and $outputPathText -match 'function New-MediaPipelineVerificationEvidence' -and $outputPathText -match 'function New-MediaPipelinePublishEvidence') 'Expected output/path planning helpers to own diagnostic consumer and post-processing evidence shaping.'

$script:LibraryProfiles = @(
    [pscustomobject]@{
        id = 'alpha'
        name = 'Alpha'
        enabled = $true
        designation = 'movie'
        source_path = 'C:\SharedLibrary'
        output_path = 'D:\AlphaProcessed'
        overrides = [pscustomobject]@{ audio = [pscustomobject]@{ AudioMaxChannels = 2 } }
    },
    [pscustomobject]@{
        id = 'beta'
        name = 'Beta'
        enabled = $true
        designation = 'movie'
        source_path = 'C:\SharedLibrary'
        output_path = 'D:\BetaProcessed'
        overrides = [pscustomobject]@{ audio = [pscustomobject]@{ AudioMaxChannels = 8 } }
    },
    [pscustomobject]@{
        id = 'separate'
        name = 'Separate'
        enabled = $true
        designation = 'movie'
        source_path = 'C:\SeparateLibrary'
        output_path = 'D:\SeparateProcessed'
        overrides = [pscustomobject]@{ audio = [pscustomobject]@{ AudioMaxChannels = 4 } }
    }
)

$selectedBetaOverrides = Resolve-MediaPipelineLibraryOverridesForPath -SourcePath 'C:\SharedLibrary\Movie.mkv' -LibraryProfileId 'beta'
Assert-Equal $selectedBetaOverrides['AudioMaxChannels'] 8 'Expected selected library profile id to win when source root matches.'
$script:CurrentLibraryProfileId = 'beta'
$selectedBetaEvidence = Get-MediaPipelineLibraryProfileEvidenceForPath -SourcePath 'C:\SharedLibrary\Movie.mkv'
Assert-Equal $selectedBetaEvidence['library_id'] 'beta' 'Expected current queue-selected library id to flow into evidence.'
Assert-Equal $selectedBetaEvidence['output_root'] 'D:\BetaProcessed' 'Expected selected library output root to flow into evidence.'

$script:CurrentLibraryProfileId = 'beta'
$separateOverrides = Resolve-MediaPipelineLibraryOverridesForPath -SourcePath 'C:\SeparateLibrary\Movie.mkv'
Assert-Equal $separateOverrides['AudioMaxChannels'] 4 'Expected mismatched selected library id not to cross source-root boundaries.'
$script:CurrentLibraryProfileId = ''

$queueItem = New-MediaQueueItem `
    -SourcePath 'E:\AnimeSource\Show\Season 01\Show - S01E01.mkv' `
    -RootPath 'E:\AnimeSource' `
    -MediaKind 'tv' `
    -LibraryId 'anime' `
    -LibraryName 'Anime' `
    -LibraryDesignation 'tv' `
    -LibraryOutputRoot 'F:\AnimeProcessed'

Assert-Equal $queueItem.LibraryId 'anime' 'Expected queue item to carry library id.'
Assert-Equal $queueItem.LibraryDesignation 'tv' 'Expected queue item to carry designation.'
Assert-Equal $queueItem.LibraryOutputRoot 'F:\AnimeProcessed' 'Expected queue item to carry output root.'

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-library-profile-test-" + [guid]::NewGuid().ToString('N'))
try {
    $movieRoot = Join-Path $tempRoot 'Movies'
    $tvRoot = Join-Path $tempRoot 'TV'
    $animeRoot = Join-Path $tempRoot 'Anime'
    $autoRoot = Join-Path $tempRoot 'Auto'
    New-Item -ItemType Directory -Path $movieRoot, $tvRoot, $animeRoot, $autoRoot -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $movieRoot 'Movie.mkv') -Force | Out-Null
    $animeSeason = Join-Path $animeRoot 'Show\Season 01'
    New-Item -ItemType Directory -Path $animeSeason -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $animeSeason 'Show - S01E01.mkv') -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $autoRoot 'Auto Movie.mkv') -Force | Out-Null
    $autoSeason = Join-Path $autoRoot 'Auto Show\Season 01'
    New-Item -ItemType Directory -Path $autoSeason -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $autoSeason 'Auto Show - S01E01.mkv') -Force | Out-Null

    $script:SourceMovies = $movieRoot
    $script:SourceTV = $tvRoot
    $script:Outsource = Join-Path $tempRoot 'Processed'
    $script:SourceScanIntervalSeconds = 0
    $script:MovieScanCache = @()
    $script:TVScanCache = @()
    $script:MovieScanCacheAt = $null
    $script:TVScanCacheAt = $null
    $script:QueueOrderingStrategy = 'Standard'
    $script:MixPriorityPhase = $false
    $script:PriorityMarkers = @('!')
    $script:LibraryProfiles = @(
        [pscustomobject]@{
            id = 'movies'
            name = 'Movies'
            enabled = $true
            designation = 'movie'
            source_path = $movieRoot
            output_path = $script:Outsource
            overrides = [pscustomobject]@{
                editor = [pscustomobject]@{ RoutingProfile = 'manual' }
                video = [pscustomobject]@{}
                subtitles = [pscustomobject]@{}
                audio = [pscustomobject]@{}
            }
        },
        [pscustomobject]@{
            id = 'anime'
            name = 'Anime'
            enabled = $true
            designation = 'tv'
            source_path = $animeRoot
            output_path = (Join-Path $tempRoot 'AnimeProcessed')
            overrides = [pscustomobject]@{
                editor = [pscustomobject]@{}
                video = [pscustomobject]@{ VideoQuality = 20 }
                subtitles = [pscustomobject]@{}
                audio = [pscustomobject]@{ AudioMaxChannels = 6 }
            }
        },
        [pscustomobject]@{
            id = 'auto'
            name = 'Auto'
            enabled = $true
            designation = 'auto'
            source_path = $autoRoot
            output_path = (Join-Path $tempRoot 'AutoProcessed')
            overrides = [pscustomobject]@{
                editor = [pscustomobject]@{ RouteThresholdMode = 'bitrate' }
                video = [pscustomobject]@{}
                subtitles = [pscustomobject]@{}
                audio = [pscustomobject]@{}
            }
        }
    )

    $discovery = Get-MediaQueueDiscoveryPlan -MovieRoot $movieRoot -TVRoot $tvRoot -ForceRefresh:$true
    Assert-Equal @($discovery.MovieEntries).Count 2 'Expected movie discovery from default movie profile plus auto movie item.'
    Assert-Equal @($discovery.TVEntries).Count 2 'Expected TV discovery from extra anime profile plus auto TV item.'
    $animeEntry = @($discovery.TVEntries | Where-Object { $_.LibraryId -eq 'anime' })[0]
    $autoMovieEntry = @($discovery.MovieEntries | Where-Object { $_.LibraryId -eq 'auto' })[0]
    $autoTvEntry = @($discovery.TVEntries | Where-Object { $_.LibraryId -eq 'auto' })[0]
    Assert-Equal ([string]$animeEntry.LibraryOutputRoot) (Join-Path $tempRoot 'AnimeProcessed') 'Expected discovery entry to carry extra output root.'
    Assert-Contains $animeEntry.Metadata['settings_override_keys'] 'AudioMaxChannels' 'Expected discovery entry to snapshot custom library audio setting keys.'
    Assert-Equal $animeEntry.Metadata['settings_overrides']['AudioMaxChannels'] 6 'Expected discovery entry to snapshot custom library setting values.'
    Assert-Equal $animeEntry.Metadata['effective_settings']['VideoQuality'] 20 'Expected discovery entry to snapshot effective library setting values.'
    Assert-Equal ([string]$autoMovieEntry.LibraryDesignation) 'auto' 'Expected auto movie entry to carry auto designation.'
    Assert-Equal ([string]$autoMovieEntry.MediaKind) 'movie' 'Expected auto movie-looking file to route as movie.'
    Assert-Equal ([string]$autoMovieEntry.LibraryOutputRoot) (Join-Path $tempRoot 'AutoProcessed') 'Expected auto movie entry to carry auto output root.'
    Assert-Contains $autoMovieEntry.Metadata['settings_override_keys'] 'RouteThresholdMode' 'Expected auto movie entry to snapshot custom library setting keys.'
    Assert-Equal ([string]$autoTvEntry.LibraryDesignation) 'auto' 'Expected auto TV entry to carry auto designation.'
    Assert-Equal ([string]$autoTvEntry.MediaKind) 'tv' 'Expected auto TV-looking file to route as TV.'
    Assert-Equal ([string]$autoTvEntry.LibraryOutputRoot) (Join-Path $tempRoot 'AutoProcessed') 'Expected auto TV entry to carry auto output root.'
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

$invalidOverrideConfig = Get-MediaPipelineConfigDefaultValues
$invalidOverrideConfig['LibraryProfiles'] = @(
    [ordered]@{
        id = 'movies'
        name = 'Movies'
        enabled = $true
        designation = 'movie'
        source_path = 'C:\Incoming\Movies'
        output_path = 'D:\Processed'
        overrides = [ordered]@{
            editor = [ordered]@{
                RouteThresholdMode = 'all'
                EncodeThresholdGB = -1
                MovieRouteMaxVideoBitrateMbps = 'many'
                TVRouteMaxVideoBitrateMbps = 0
            }
        }
    },
    [ordered]@{
        id = 'tv'
        name = 'TV'
        enabled = $true
        designation = 'tv'
        source_path = 'C:\Incoming\TV'
        output_path = 'D:\Processed'
        overrides = [ordered]@{}
    }
)
$invalidOverrideResult = Test-MediaPipelineConfigSchema -Config $invalidOverrideConfig
$invalidOverrideErrors = (@($invalidOverrideResult.Errors) -join "`n")
Assert-True (-not [bool]$invalidOverrideResult.Ok) 'Expected invalid library route overrides to fail config validation.'
Assert-True ($invalidOverrideErrors -match 'Library profile Movies override is invalid: RouteThresholdMode must be one of') 'Expected invalid RouteThresholdMode override error.'
Assert-True ($invalidOverrideErrors -match 'Library profile Movies override is invalid: MovieRouteMaxVideoBitrateMbps must be an integer') 'Expected malformed movie bitrate override error.'
Assert-True ($invalidOverrideErrors -match 'Library profile Movies override is invalid: TVRouteMaxVideoBitrateMbps must be between 1 and 500') 'Expected zero TV bitrate override error.'
Assert-True ($invalidOverrideErrors -match 'Library profile Movies override is invalid: EncodeThresholdGB must be at least 1') 'Expected negative size threshold override error.'

$duplicateRootConfig = Get-MediaPipelineConfigDefaultValues
$duplicateRootConfig['LibraryProfiles'] = @(
    [ordered]@{ id = 'movies'; name = 'Movies'; enabled = $true; designation = 'movie'; source_path = 'C:\Incoming\Movies'; output_path = 'D:\Processed'; overrides = [ordered]@{} },
    [ordered]@{ id = 'tv'; name = 'TV'; enabled = $true; designation = 'tv'; source_path = 'C:\Incoming\TV'; output_path = 'D:\Processed'; overrides = [ordered]@{} },
    [ordered]@{ id = 'alpha'; name = 'Alpha'; enabled = $true; designation = 'movie'; source_path = 'C:\SharedLibrary'; output_path = 'D:\AlphaProcessed'; overrides = [ordered]@{} },
    [ordered]@{ id = 'beta'; name = 'Beta'; enabled = $true; designation = 'movie'; source_path = 'C:\SharedLibrary'; output_path = 'D:\BetaProcessed'; overrides = [ordered]@{} }
)
$duplicateRootResult = Test-MediaPipelineConfigSchema -Config $duplicateRootConfig
$duplicateRootErrors = (@($duplicateRootResult.Errors) -join "`n")
Assert-True (-not [bool]$duplicateRootResult.Ok) 'Expected duplicate enabled library source roots to fail config validation.'
Assert-True ($duplicateRootErrors -match 'Beta shares an enabled source root with Alpha') 'Expected duplicate enabled source root error.'

Write-Host 'Library profile routing checks passed.'
