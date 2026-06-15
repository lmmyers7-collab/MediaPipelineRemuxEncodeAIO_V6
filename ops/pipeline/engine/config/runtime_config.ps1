# ==============================================================================
# ops\pipeline\engine\config\runtime_config.ps1
# ==============================================================================
# Config resolution support for ops\pipeline\entrypoints\MediaPipeline.ps1.
#
# Dot-sourced so functions resolve the caller's $config / $script:* runtime
# variables by dynamic scope at call time (same convention as the Get-Config*
# getters in ops\pipeline\engine\config\getters.ps1).
#
# Phase 0 of the config-loader extraction (ADR / SESSION 2026-06-03):
#   Get-MediaPipelineResolvedConfigDump -- a complete, deterministic snapshot of
#   every config-derived runtime value. Used as a parity oracle to prove the
#   later resolver extraction is behaviour-neutral, and as operator-facing
#   "what did this run actually resolve" diagnostics. Read-only; no side effects.
# ==============================================================================

$runtimeConfigModuleRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $PSCommandPath }
. (Join-Path $runtimeConfigModuleRoot 'runtime_paths.ps1')
. (Join-Path $runtimeConfigModuleRoot 'runtime_merge.ps1')
. (Join-Path $runtimeConfigModuleRoot 'runtime_validation.ps1')

function Initialize-MediaPipelineRuntimeConfig {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] $Config,
        [Parameter(Mandatory)] $SchemaResult
    )

    # Inputs aliased to the names the moved block already uses so the
    # transcribed config-resolution logic runs verbatim. Because this module is
    # dot-sourced, $script:* and Set-Variable -Scope Script assignments below
    # land in the MediaPipeline.ps1 script scope, exactly as the inline block
    # did. Moved from MediaPipeline.ps1 (config value resolution) 2026-06-03.
    $config = $Config
    $configSchemaCheck = $SchemaResult
    $arrayKeys = @($SchemaResult.ArrayKeys)
Set-MediaPipelineRuntimeConfigVariables -Config $config -ArrayKeys $arrayKeys
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
$script:BdpgsOcrToolPath = if ($config.ContainsKey('BdpgsOcrToolPath')) { [string]$config['BdpgsOcrToolPath'] } else { 'tools\PgsToSrt\PgsToSrt.exe' }
$script:BdpgsOcrTessdataPath = if ($config.ContainsKey('BdpgsOcrTessdataPath')) { [string]$config['BdpgsOcrTessdataPath'] } else { 'tools\PgsToSrt\tessdata' }
$script:ConvertVobSubToSrt = Get-ConfigBool 'ConvertVobSubToSrt' $false
$script:DropVobSubAfterConversion = Get-ConfigBool 'DropVobSubAfterConversion' $false
$script:TreatVobSubSignsSongsAsForced = Get-ConfigBool 'TreatVobSubSignsSongsAsForced' $false
$script:VobSubOcrToolPath = if ($config.ContainsKey('VobSubOcrToolPath')) { [string]$config['VobSubOcrToolPath'] } else { 'tools\SubtitleEditLegacy\SubtitleEdit.exe' }
$script:TreatAssSignsSongsAsForced = Get-ConfigBool 'TreatAssSignsSongsAsForced' $false
$script:TreatTx3gSignsSongsAsForced = Get-ConfigBool 'TreatTx3gSignsSongsAsForced' $false
$script:AggressiveEpisodeParsing = Get-ConfigBool 'AggressiveEpisodeParsing' $false
$script:AllowSystemTools = Get-ConfigBool 'AllowSystemTools' $false
$script:DoviToolPath = if ($config.ContainsKey('DoviToolPath')) { [string]$config['DoviToolPath'] } else { '' }
$script:Hdr10PlusToolPath = if ($config.ContainsKey('Hdr10PlusToolPath')) { [string]$config['Hdr10PlusToolPath'] } else { '' }
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
$script:EnableQualityVerification    = Get-ConfigBool 'EnableQualityVerification' $false
$script:QualityMetric = if ($config.ContainsKey('QualityMetric')) {
    Resolve-MediaPipelineQualityMetric -Metric ([string]$config['QualityMetric'])
} else {
    Get-MediaPipelineQualityMetricDefault
}
$script:QualitySampleMode = if ($config.ContainsKey('QualitySampleMode')) {
    Resolve-MediaPipelineQualitySampleMode -Mode ([string]$config['QualitySampleMode'])
} else {
    Get-MediaPipelineQualitySampleModeDefault
}
$script:QualitySampleSeconds          = Get-ConfigInt 'QualitySampleSeconds' 10 2 60
$script:QualitySampleCount            = Get-ConfigInt 'QualitySampleCount' 3 1 10
$script:QualityWarnThreshold          = Get-ConfigDouble 'QualityWarnThreshold' 90 0 ([double]::MaxValue)
$script:QualityFailThreshold          = Get-ConfigDouble 'QualityFailThreshold' 75 0 ([double]::MaxValue)
$script:QualityFailAction = if ($config.ContainsKey('QualityFailAction')) {
    Resolve-MediaPipelineQualityFailAction -Action ([string]$config['QualityFailAction'])
} else {
    Get-MediaPipelineQualityFailActionDefault
}
$script:QualityVerifyTimeoutSeconds   = Get-ConfigInt 'QualityVerifyTimeoutSeconds' 1800 60 21600
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
    else                             { $script:ExcludeSubtitleStyles = @($v) }
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
    else                        { $script:IncludeSubtitleStyles = @($v) }
} else {
    $script:IncludeSubtitleStyles = @()
}

if ($config.ContainsKey('Tx3gExtractLanguages')) {
    $v = $config['Tx3gExtractLanguages']
    if     ($null -eq $v)       { $script:Tx3gExtractLanguages = @() }
    else                        { $script:Tx3gExtractLanguages = @($v) }
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
    else                        { $script:BdpgsExtractLanguages = @($v) }
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
    else                        { $script:VobSubExtractLanguages = @($v) }
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
    else                        { $script:PriorityMarkers = @($v) }
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
    else                        { $script:PreferredDefaultAudioLanguages = @($v) }
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
$script:DynamicHdrPolicy = if ($config.ContainsKey('DynamicHdrPolicy')) {
    Resolve-MediaPipelineDynamicHdrPolicy -Policy ([string]$config['DynamicHdrPolicy'])
} else {
    Get-MediaPipelineDynamicHdrPolicyDefault
}
$removedRoutingFallbackConfigKeys = @(
    'EncodeThresholdGB',
    'TVEncodeThresholdGB',
    'MovieRouteMaxVideoBitrateMbps',
    'TVRouteMaxVideoBitrateMbps',
    'Route1080pBucketMaxHeight',
    'Route4KBucketMinHeight'
)
foreach ($removedKey in $removedRoutingFallbackConfigKeys) {
    if ($config.ContainsKey($removedKey)) {
        Add-StartupWarning "$removedKey is obsolete and ignored; use per-height target sizes, bitrate caps, and tolerance percents."
    }
}
$script:MovieRoute1080pTargetSizeGB = Get-ConfigDouble 'MovieRoute1080pTargetSizeGB' 8 1 1000000
$script:MovieRoute1440pTargetSizeGB = Get-ConfigDouble 'MovieRoute1440pTargetSizeGB' 8 1 1000000
$script:MovieRoute4KTargetSizeGB = Get-ConfigDouble 'MovieRoute4KTargetSizeGB' 8 1 1000000
$script:TVRoute1080pTargetSizeGB = Get-ConfigDouble 'TVRoute1080pTargetSizeGB' 3 1 1000000
$script:TVRoute1440pTargetSizeGB = Get-ConfigDouble 'TVRoute1440pTargetSizeGB' 3 1 1000000
$script:TVRoute4KTargetSizeGB = Get-ConfigDouble 'TVRoute4KTargetSizeGB' 3 1 1000000
$script:Route1080pUpperHeightTolerancePercent = Get-ConfigDouble 'Route1080pUpperHeightTolerancePercent' 11.111111 0 100
$script:Route1080pMaxVideoBitrateMbps = Get-ConfigDouble 'Route1080pMaxVideoBitrateMbps' 20 1 500
$script:Route1440pLowerHeightTolerancePercent = Get-ConfigDouble 'Route1440pLowerHeightTolerancePercent' 16.597222 0 100
$script:Route1440pUpperHeightTolerancePercent = Get-ConfigDouble 'Route1440pUpperHeightTolerancePercent' 24.930556 0 100
$script:Route1440pMaxVideoBitrateMbps = Get-ConfigDouble 'Route1440pMaxVideoBitrateMbps' 35 1 500
$script:Route4KLowerHeightTolerancePercent = Get-ConfigDouble 'Route4KLowerHeightTolerancePercent' 16.666667 0 100
$script:Route4KMaxVideoBitrateMbps = Get-ConfigDouble 'Route4KMaxVideoBitrateMbps' 35 1 500
$routeHeightBoundaries = Get-MediaPipelineRouteHeightToleranceBoundaries `
    -Route1080pUpperHeightTolerancePercent $script:Route1080pUpperHeightTolerancePercent `
    -Route1440pLowerHeightTolerancePercent $script:Route1440pLowerHeightTolerancePercent `
    -Route1440pUpperHeightTolerancePercent $script:Route1440pUpperHeightTolerancePercent `
    -Route4KLowerHeightTolerancePercent $script:Route4KLowerHeightTolerancePercent
if (-not $routeHeightBoundaries.IsContiguous) {
    Add-StartupWarning 'Height tolerance boundaries must be contiguous; using default bucket boundaries 1200/1800.'
    $script:Route1080pUpperHeightTolerancePercent = 11.111111
    $script:Route1440pLowerHeightTolerancePercent = 16.597222
    $script:Route1440pUpperHeightTolerancePercent = 24.930556
    $script:Route4KLowerHeightTolerancePercent = 16.666667
    $routeHeightBoundaries = Get-MediaPipelineRouteHeightToleranceBoundaries
}
$script:Route1080pBucketMaxHeight = [int]$routeHeightBoundaries.Route1080pMaxHeight
$script:Route4KBucketMinHeight = [int]$routeHeightBoundaries.Route4KMinHeight
$script:AllowH264RemuxIfPlexCompatible = Get-ConfigBool 'AllowH264RemuxIfPlexCompatible' $true
$script:H264RemuxMaxBitrateMbps = Get-ConfigDouble 'H264RemuxMaxBitrateMbps' 35 1 500
$script:H264RemuxMaxHeight = Get-ConfigInt 'H264RemuxMaxHeight' 1080 1 4320
$script:MaxEncodeGrowthPercent = Get-ConfigDouble 'MaxEncodeGrowthPercent' 5 0 1000
$script:CompatibilityEncodeGrowthPercent = Get-ConfigDouble 'CompatibilityEncodeGrowthPercent' 15 0 1000
$script:CurrentSizePolicyResult = $null
$script:LastQualityVerification = $null
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
# BitrateForChannels in ops\pipeline\engine\audio\audio.ps1 for the table.
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
# Resolve-MediaPipelineCpuEncodePreset (ops\pipeline\engine\config\config_schema.ps1).
$script:CpuEncodePreset = if ($config.ContainsKey('CpuEncodePreset')) {
    Resolve-MediaPipelineCpuEncodePreset -Preset ([string]$config['CpuEncodePreset'])
} else {
    Get-MediaPipelineCpuEncodePresetDefault
}

# Windows ProcessPriorityClass to apply to ffmpeg when running a CPU encode.
# 'belownormal' keeps the desktop UI responsive while libx265 saturates cores;
# 'inherit' leaves the priority alone (legacy behavior).  Validation lives in
# Resolve-MediaPipelineCpuEncodeProcessPriority (ops\pipeline\engine\config\config_schema.ps1).
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

Invoke-MediaPipelineRuntimeConfigLogicalValidation


}
