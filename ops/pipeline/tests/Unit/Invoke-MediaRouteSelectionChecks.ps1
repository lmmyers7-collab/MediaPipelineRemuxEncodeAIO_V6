param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSScriptRoot."
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -PathType Container)) {
    throw "Resolved repository root is missing ops\pipeline\engine: $repoRoot"
}
. (Join-Path $repoRoot 'ops\pipeline\engine\shared\media_constants.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\decide\routing.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\decide\encode_policy.ps1')

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

function Assert-True {
    param(
        [Parameter(Mandatory)] [bool] $Condition,
        [Parameter(Mandatory)] [string] $Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-Near {
    param(
        [Parameter(Mandatory)] [double] $Actual,
        [Parameter(Mandatory)] [double] $Expected,
        [double] $Tolerance = 0.001,
        [Parameter(Mandatory)] [string] $Message
    )
    if ([math]::Abs($Actual - $Expected) -gt $Tolerance) {
        throw "$Message Expected '$Expected' but got '$Actual'."
    }
}

function Get-TraceCodes {
    param($Plan)
    return @($Plan.DecisionTrace | ForEach-Object { [string]$_.code })
}

function Assert-TraceContains {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string] $Code,
        [Parameter(Mandatory)] [string] $Message
    )
    $codes = Get-TraceCodes -Plan $Plan
    if (-not ($codes -contains $Code)) {
        throw "$Message Trace codes: $($codes -join ', ')"
    }
}

function Get-RoutingTraceData {
    param($Plan)
    $entry = @($Plan.DecisionTrace | Where-Object { [string]$_.code -eq 'routing_profile_selected' } | Select-Object -First 1)
    if (-not $entry) { return $null }
    return $entry[0].data
}

$movieThreshold = 8.0
$tvThreshold = 3.0
$movieBitrateThreshold = 35.0
$tvBitrateThreshold = 18.0
$route1080pThreshold = 20.0
$route1440pThreshold = 35.0
$route4kThreshold = 35.0

$inputs = @(
    @{
        Name = 'small 1080p low-bitrate'
        SizeBytes = [long](4 * 1GB)
        DurationSeconds = 7200.0
        Height = 1080
        ExpectedEstimatedMbps = [math]::Round((([double]([long](4 * 1GB)) * 8.0) / 7200.0) / 1000000.0, 3)
        ExpectedBitrateThreshold = $route1080pThreshold
        ExpectedBitrateBucket = '1080p'
        ExpectedSizeOver = $false
        ExpectedBitrateOver = $false
        Expected = @{
            compatibility_advisory = @{ Route = 'remux'; ReasonCode = 'size_within_threshold' }
            size = @{ Route = 'remux'; ReasonCode = 'size_within_threshold' }
            bitrate = @{ Route = 'remux'; ReasonCode = 'size_within_threshold' }
            size_or_bitrate = @{ Route = 'remux'; ReasonCode = 'size_within_threshold' }
        }
    },
    @{
        Name = 'large 1080p high-bitrate'
        SizeBytes = [long](10 * 1GB)
        DurationSeconds = 1800.0
        Height = 1080
        ExpectedEstimatedMbps = [math]::Round((([double]([long](10 * 1GB)) * 8.0) / 1800.0) / 1000000.0, 3)
        ExpectedBitrateThreshold = $route1080pThreshold
        ExpectedBitrateBucket = '1080p'
        ExpectedSizeOver = $true
        ExpectedBitrateOver = $true
        Expected = @{
            compatibility_advisory = @{ Route = 'encode'; ReasonCode = 'bitrate_over_threshold' }
            size = @{ Route = 'encode'; ReasonCode = 'size_over_threshold' }
            bitrate = @{ Route = 'encode'; ReasonCode = 'bitrate_over_threshold' }
            size_or_bitrate = @{ Route = 'encode'; ReasonCode = 'bitrate_over_threshold' }
        }
    },
    @{
        Name = '4K low-bitrate'
        SizeBytes = [long](4 * 1GB)
        DurationSeconds = 7200.0
        Height = 2160
        ExpectedEstimatedMbps = [math]::Round((([double]([long](4 * 1GB)) * 8.0) / 7200.0) / 1000000.0, 3)
        ExpectedBitrateThreshold = $route4kThreshold
        ExpectedBitrateBucket = '4k'
        ExpectedSizeOver = $false
        ExpectedBitrateOver = $false
        Expected = @{
            compatibility_advisory = @{ Route = 'remux'; ReasonCode = 'size_within_threshold' }
            size = @{ Route = 'remux'; ReasonCode = 'size_within_threshold' }
            bitrate = @{ Route = 'remux'; ReasonCode = 'size_within_threshold' }
            size_or_bitrate = @{ Route = 'remux'; ReasonCode = 'size_within_threshold' }
        }
    },
    @{
        Name = '4K high-bitrate'
        SizeBytes = [long](10 * 1GB)
        DurationSeconds = 1800.0
        Height = 2160
        ExpectedEstimatedMbps = [math]::Round((([double]([long](10 * 1GB)) * 8.0) / 1800.0) / 1000000.0, 3)
        ExpectedBitrateThreshold = $route4kThreshold
        ExpectedBitrateBucket = '4k'
        ExpectedSizeOver = $true
        ExpectedBitrateOver = $true
        Expected = @{
            compatibility_advisory = @{ Route = 'encode'; ReasonCode = 'bitrate_over_threshold' }
            size = @{ Route = 'encode'; ReasonCode = 'size_over_threshold' }
            bitrate = @{ Route = 'encode'; ReasonCode = 'bitrate_over_threshold' }
            size_or_bitrate = @{ Route = 'encode'; ReasonCode = 'bitrate_over_threshold' }
        }
    },
    @{
        Name = 'in-between height low-bitrate'
        SizeBytes = [long](4 * 1GB)
        DurationSeconds = 7200.0
        Height = 1600
        ExpectedEstimatedMbps = [math]::Round((([double]([long](4 * 1GB)) * 8.0) / 7200.0) / 1000000.0, 3)
        ExpectedBitrateThreshold = $route1440pThreshold
        ExpectedBitrateBucket = '1440p'
        ExpectedSizeOver = $false
        ExpectedBitrateOver = $false
        Expected = @{
            compatibility_advisory = @{ Route = 'remux'; ReasonCode = 'size_within_threshold' }
            size = @{ Route = 'remux'; ReasonCode = 'size_within_threshold' }
            bitrate = @{ Route = 'remux'; ReasonCode = 'size_within_threshold' }
            size_or_bitrate = @{ Route = 'remux'; ReasonCode = 'size_within_threshold' }
        }
    }
)

foreach ($mode in @('compatibility_advisory','size','bitrate','size_or_bitrate')) {
    foreach ($inputCase in $inputs) {
        $plan = Resolve-MediaRouteBySize `
            -FileSizeBytes ([long]$inputCase.SizeBytes) `
            -IsTV:$false `
            -MovieRoute1080pTargetSizeGB $movieThreshold `
            -MovieRoute1440pTargetSizeGB $movieThreshold `
            -MovieRoute4KTargetSizeGB $movieThreshold `
            -TVRoute1080pTargetSizeGB $tvThreshold `
            -TVRoute1440pTargetSizeGB $tvThreshold `
            -TVRoute4KTargetSizeGB $tvThreshold `
            -DurationSeconds ([double]$inputCase.DurationSeconds) `
            -VideoCodec 'hevc' `
            -VideoHeight ([int]$inputCase.Height) `
            -RoutingProfile 'plex_direct_stream' `
            -RouteThresholdMode $mode

        $expected = $inputCase.Expected[$mode]
        $label = "$mode / $($inputCase.Name)"
        Assert-Equal ([string]$plan.Route) ([string]$expected.Route) "$label route mismatch."
        Assert-Equal ([string]$plan.ReasonCode) ([string]$expected.ReasonCode) "$label reason code mismatch."
        Assert-Near ([double]$plan.EstimatedBitrateMbps) ([double]$inputCase.ExpectedEstimatedMbps) -Message "$label estimated bitrate mismatch."
        Assert-Near ([double]$plan.ThresholdGB) $movieThreshold -Message "$label size threshold mismatch."
        Assert-Near ([double]$plan.BitrateThresholdMbps) ([double]$inputCase.ExpectedBitrateThreshold) -Message "$label bitrate threshold mismatch."
        Assert-Equal ([bool]$plan.SizeOverThreshold) ([bool]$inputCase.ExpectedSizeOver) "$label size-over-threshold mismatch."
        Assert-Equal ([bool]$plan.BitrateOverThreshold) ([bool]$inputCase.ExpectedBitrateOver) "$label bitrate-over-threshold mismatch."
        Assert-TraceContains -Plan $plan -Code 'routing_profile_selected' -Message "$label missing profile trace."
        $routingData = Get-RoutingTraceData -Plan $plan
        Assert-Equal ([string]$routingData.route_bitrate_source) 'source_height_bucket' "$label route bitrate source mismatch."
        Assert-Equal ([string]$routingData.route_bitrate_bucket) ([string]$inputCase.ExpectedBitrateBucket) "$label route bitrate bucket mismatch."
        Assert-Equal ([string]$routingData.route_size_source) 'source_height_bucket_movie' "$label route size source mismatch."
        Assert-Equal ([string]$routingData.route_size_bucket) ([string]$inputCase.ExpectedBitrateBucket) "$label route size bucket mismatch."
        Assert-TraceContains -Plan $plan -Code 'size_evaluated' -Message "$label missing size trace."
        Assert-TraceContains -Plan $plan -Code 'bitrate_estimated' -Message "$label missing bitrate trace."
        Assert-TraceContains -Plan $plan -Code ([string]$expected.ReasonCode) -Message "$label missing final reason trace."
    }
}

foreach ($boundaryCase in @(
    @{ Height = 1200; ExpectedBucket = '1080p'; ExpectedCap = 21.0 },
    @{ Height = 1201; ExpectedBucket = '1440p'; ExpectedCap = 31.0 },
    @{ Height = 1799; ExpectedBucket = '1440p'; ExpectedCap = 31.0 },
    @{ Height = 1800; ExpectedBucket = '4k'; ExpectedCap = 41.0 }
)) {
    $boundaryPlan = Resolve-MediaRouteBySize `
        -FileSizeBytes ([long](4 * 1GB)) `
        -IsTV:$false `
        -MovieRoute1080pTargetSizeGB 80 `
        -MovieRoute1440pTargetSizeGB 80 `
        -MovieRoute4KTargetSizeGB 80 `
        -TVRoute1080pTargetSizeGB 50 `
        -TVRoute1440pTargetSizeGB 50 `
        -TVRoute4KTargetSizeGB 50 `
        -DurationSeconds 7200 `
        -VideoCodec 'hevc' `
        -VideoHeight ([int]$boundaryCase.Height) `
        -RoutingProfile 'plex_direct_stream' `
        -RouteThresholdMode 'bitrate' `
        -Route1080pMaxVideoBitrateMbps 21 `
        -Route1440pMaxVideoBitrateMbps 31 `
        -Route4KMaxVideoBitrateMbps 41
    $boundaryTrace = Get-RoutingTraceData -Plan $boundaryPlan
    Assert-Equal ([string]$boundaryTrace.route_bitrate_bucket) ([string]$boundaryCase.ExpectedBucket) "Boundary height $($boundaryCase.Height) route bucket mismatch."
    Assert-Near ([double]$boundaryTrace.route_max_bitrate_mbps) ([double]$boundaryCase.ExpectedCap) -Message "Boundary height $($boundaryCase.Height) bitrate cap mismatch."
}

foreach ($sizeCase in @(
    @{ IsTV = $false; Height = 1080; ExpectedBucket = '1080p'; ExpectedTarget = 7.0; ExpectedSource = 'source_height_bucket_movie' },
    @{ IsTV = $false; Height = 1440; ExpectedBucket = '1440p'; ExpectedTarget = 11.0; ExpectedSource = 'source_height_bucket_movie' },
    @{ IsTV = $false; Height = 2160; ExpectedBucket = '4k'; ExpectedTarget = 17.0; ExpectedSource = 'source_height_bucket_movie' },
    @{ IsTV = $true; Height = 1080; ExpectedBucket = '1080p'; ExpectedTarget = 2.0; ExpectedSource = 'source_height_bucket_tv' },
    @{ IsTV = $true; Height = 1440; ExpectedBucket = '1440p'; ExpectedTarget = 5.0; ExpectedSource = 'source_height_bucket_tv' },
    @{ IsTV = $true; Height = 2160; ExpectedBucket = '4k'; ExpectedTarget = 9.0; ExpectedSource = 'source_height_bucket_tv' },
    @{ IsTV = $false; Height = 0; ExpectedBucket = '1080p'; ExpectedTarget = 7.0; ExpectedSource = 'unknown_height_1080p_bucket_movie' },
    @{ IsTV = $true; Height = 0; ExpectedBucket = '1080p'; ExpectedTarget = 2.0; ExpectedSource = 'unknown_height_1080p_bucket_tv' }
)) {
    $sizePlan = Resolve-MediaRouteBySize `
        -FileSizeBytes ([long](3 * 1GB)) `
        -IsTV:([bool]$sizeCase.IsTV) `
        -MovieRoute1080pTargetSizeGB 7 `
        -MovieRoute1440pTargetSizeGB 11 `
        -MovieRoute4KTargetSizeGB 17 `
        -TVRoute1080pTargetSizeGB 2 `
        -TVRoute1440pTargetSizeGB 5 `
        -TVRoute4KTargetSizeGB 9 `
        -DurationSeconds 7200 `
        -VideoCodec 'hevc' `
        -VideoHeight ([int]$sizeCase.Height) `
        -RoutingProfile 'plex_direct_stream' `
        -RouteThresholdMode 'size' `
        -Route1080pMaxVideoBitrateMbps 100 `
        -Route1440pMaxVideoBitrateMbps 100 `
        -Route4KMaxVideoBitrateMbps 100
    $sizeTrace = Get-RoutingTraceData -Plan $sizePlan
    Assert-Near ([double]$sizePlan.ThresholdGB) ([double]$sizeCase.ExpectedTarget) -Message "Resolution size target mismatch for height $($sizeCase.Height), IsTV=$($sizeCase.IsTV)."
    Assert-Equal ([string]$sizeTrace.route_size_bucket) ([string]$sizeCase.ExpectedBucket) "Resolution size bucket mismatch for height $($sizeCase.Height), IsTV=$($sizeCase.IsTV)."
    Assert-Equal ([string]$sizeTrace.route_size_source) ([string]$sizeCase.ExpectedSource) "Resolution size source mismatch for height $($sizeCase.Height), IsTV=$($sizeCase.IsTV)."
}

$unknownHeightMovie = Resolve-MediaRouteBySize `
    -FileSizeBytes ([long]27000000000) `
    -IsTV:$false `
    -MovieRoute1080pTargetSizeGB 50 `
    -MovieRoute1440pTargetSizeGB 50 `
    -MovieRoute4KTargetSizeGB 50 `
    -TVRoute1080pTargetSizeGB 50 `
    -TVRoute1440pTargetSizeGB 50 `
    -TVRoute4KTargetSizeGB 50 `
    -DurationSeconds 7200 `
    -VideoCodec 'hevc' `
    -VideoHeight 0 `
    -RoutingProfile 'plex_direct_stream' `
    -RouteThresholdMode 'bitrate' `
    -Route1080pMaxVideoBitrateMbps 22
Assert-Equal ([string]$unknownHeightMovie.Route) 'encode' 'Unknown-height movie should use 1080p cap and encode over 22 Mbps.'
Assert-Near ([double]$unknownHeightMovie.BitrateThresholdMbps) 22.0 -Message 'Unknown-height movie 1080p bitrate mismatch.'
$unknownMovieTrace = Get-RoutingTraceData -Plan $unknownHeightMovie
Assert-Equal ([string]$unknownMovieTrace.route_bitrate_source) 'unknown_height_1080p_bucket' 'Unknown-height movie should report 1080p bucket bitrate source.'
Assert-Equal ([string]$unknownMovieTrace.route_bitrate_bucket) '1080p' 'Unknown-height movie bucket mismatch.'

$unknownHeightTv = Resolve-MediaRouteBySize `
    -FileSizeBytes ([long]27000000000) `
    -IsTV:$true `
    -MovieRoute1080pTargetSizeGB 50 `
    -MovieRoute1440pTargetSizeGB 50 `
    -MovieRoute4KTargetSizeGB 50 `
    -TVRoute1080pTargetSizeGB 50 `
    -TVRoute1440pTargetSizeGB 50 `
    -TVRoute4KTargetSizeGB 50 `
    -DurationSeconds 7200 `
    -VideoCodec 'hevc' `
    -VideoHeight 0 `
    -RoutingProfile 'plex_direct_stream' `
    -RouteThresholdMode 'bitrate' `
    -Route1080pMaxVideoBitrateMbps 22
Assert-Equal ([string]$unknownHeightTv.Route) 'encode' 'Unknown-height TV should use 1080p cap and encode over 22 Mbps.'
Assert-Near ([double]$unknownHeightTv.BitrateThresholdMbps) 22.0 -Message 'Unknown-height TV 1080p bitrate mismatch.'
$unknownTvTrace = Get-RoutingTraceData -Plan $unknownHeightTv
Assert-Equal ([string]$unknownTvTrace.route_bitrate_source) 'unknown_height_1080p_bucket' 'Unknown-height TV should report 1080p bucket bitrate source.'
Assert-Equal ([string]$unknownTvTrace.route_bitrate_bucket) '1080p' 'Unknown-height TV bucket mismatch.'

$folderBitrateOverride = Resolve-MediaRouteBySize `
    -FileSizeBytes ([long]27000000000) `
    -IsTV:$false `
    -MovieRoute1080pTargetSizeGB 50 `
    -MovieRoute1440pTargetSizeGB 50 `
    -MovieRoute4KTargetSizeGB 50 `
    -TVRoute1080pTargetSizeGB 50 `
    -TVRoute1440pTargetSizeGB 50 `
    -TVRoute4KTargetSizeGB 50 `
    -DurationSeconds 7200 `
    -VideoCodec 'hevc' `
    -VideoHeight 1080 `
    -RoutingProfile 'plex_direct_stream' `
    -RouteThresholdMode 'bitrate' `
    -RouteHints @{ max_video_bitrate_mbps = 35 }
Assert-Equal ([string]$folderBitrateOverride.Route) 'remux' 'Folder explicit bitrate cap should win over the 1080-ish bucket cap.'
Assert-Near ([double]$folderBitrateOverride.BitrateThresholdMbps) 35.0 -Message 'Folder explicit bitrate threshold mismatch.'
$folderTrace = Get-RoutingTraceData -Plan $folderBitrateOverride
Assert-Equal ([string]$folderTrace.route_bitrate_source) 'folder_policy' 'Folder explicit bitrate source mismatch.'
Assert-Equal ([string]$folderTrace.route_bitrate_bucket) 'explicit_override' 'Folder explicit bitrate bucket mismatch.'

$h264FourK = Resolve-MediaRouteBySize `
    -FileSizeBytes ([long](4 * 1GB)) `
    -IsTV:$false `
    -MovieRoute1080pTargetSizeGB $movieThreshold `
    -MovieRoute1440pTargetSizeGB $movieThreshold `
    -MovieRoute4KTargetSizeGB $movieThreshold `
    -TVRoute1080pTargetSizeGB $tvThreshold `
    -TVRoute1440pTargetSizeGB $tvThreshold `
    -TVRoute4KTargetSizeGB $tvThreshold `
    -DurationSeconds 7200 `
    -VideoCodec 'h264' `
    -VideoHeight 2160 `
    -RoutingProfile 'plex_direct_stream' `
    -RouteThresholdMode 'compatibility_advisory' `
    -H264RemuxMaxHeight 1080 `
    -H264RemuxMaxBitrateMbps 35
Assert-Equal ([string]$h264FourK.Route) 'remux' 'H.264 4K should initially stay remux pending codec check.'
Assert-Equal ([string]$h264FourK.ReasonCode) 'size_within_threshold' 'H.264 4K should not use the Plex-compatible H.264 shortcut.'
Assert-True (-not ((Get-TraceCodes -Plan $h264FourK) -contains 'plex_compatible_h264_remux')) 'H.264 4K unexpectedly used Plex-compatible shortcut.'

$h264FourKFinal = Resolve-RemuxCodecRoutePlan -SourceCodec 'h264' -RemuxSafeVideoCodecs @('h264','hevc') -BasePlan $h264FourK
Assert-Equal ([string]$h264FourKFinal.Route) 'remux' 'H.264 4K should still remux when codec-safe fallback allows it.'
Assert-Equal ([string]$h264FourKFinal.ReasonCode) 'codec_remux_safe' 'H.264 4K codec-safe fallback reason mismatch.'
Assert-TraceContains -Plan $h264FourKFinal -Code 'codec_remux_safe' -Message 'H.264 4K final route missing codec-safe trace.'

$h264OverBitrateSizeOnly = Resolve-MediaRouteBySize `
    -FileSizeBytes ([long](4 * 1GB)) `
    -IsTV:$false `
    -MovieRoute1080pTargetSizeGB $movieThreshold `
    -MovieRoute1440pTargetSizeGB $movieThreshold `
    -MovieRoute4KTargetSizeGB $movieThreshold `
    -TVRoute1080pTargetSizeGB $tvThreshold `
    -TVRoute1440pTargetSizeGB $tvThreshold `
    -TVRoute4KTargetSizeGB $tvThreshold `
    -DurationSeconds 900 `
    -VideoCodec 'h264' `
    -VideoHeight 1080 `
    -RoutingProfile 'plex_direct_stream' `
    -RouteThresholdMode 'size' `
    -H264RemuxMaxBitrateMbps 10
Assert-Equal ([string]$h264OverBitrateSizeOnly.Route) 'remux' 'H.264 over bitrate should still remux when size-only mode does not force encode.'
Assert-Equal ([string]$h264OverBitrateSizeOnly.ReasonCode) 'size_within_threshold' 'H.264 over bitrate in size-only mode should keep size route reason.'
Assert-Equal ([bool]$h264OverBitrateSizeOnly.BitrateOverThreshold) $true 'H.264 over bitrate evidence should still be exposed.'
Assert-TraceContains -Plan $h264OverBitrateSizeOnly -Code 'bitrate_threshold_ignored' -Message 'H.264 size-only route should trace ignored bitrate threshold.'

$missingDuration = Resolve-MediaRouteBySize `
    -FileSizeBytes ([long](4 * 1GB)) `
    -IsTV:$false `
    -MovieRoute1080pTargetSizeGB $movieThreshold `
    -MovieRoute1440pTargetSizeGB $movieThreshold `
    -MovieRoute4KTargetSizeGB $movieThreshold `
    -TVRoute1080pTargetSizeGB $tvThreshold `
    -TVRoute1440pTargetSizeGB $tvThreshold `
    -TVRoute4KTargetSizeGB $tvThreshold `
    -DurationSeconds 0 `
    -VideoCodec 'hevc' `
    -VideoHeight 1080 `
    -RoutingProfile 'plex_direct_stream' `
    -RouteThresholdMode 'bitrate' `
    -SourceMediaProfile @{ estimated_bitrate_mbps = 80.0; duration_seconds = 0 }
Assert-Equal ([string]$missingDuration.Route) 'remux' 'Missing duration should not force bitrate encode from source_media_profile estimated bitrate.'
Assert-Equal ([string]$missingDuration.ReasonCode) 'size_within_threshold' 'Missing duration should preserve size-within route reason.'
Assert-Near ([double]$missingDuration.EstimatedBitrateMbps) 0.0 -Message 'Missing duration should report zero route-estimated bitrate.'
Assert-Equal ([bool]$missingDuration.BitrateOverThreshold) $false 'Missing duration should not mark bitrate over threshold.'
Assert-True (-not ((Get-TraceCodes -Plan $missingDuration) -contains 'bitrate_over_threshold')) 'Missing duration unexpectedly fired bitrate_over_threshold.'
Assert-True (-not ((Get-TraceCodes -Plan $missingDuration) -contains 'bitrate_estimated')) 'Missing duration unexpectedly emitted bitrate_estimated trace.'

$sizePolicyRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-size-policy-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $sizePolicyRoot | Out-Null
try {
    $sizePolicySourcePath = Join-Path $sizePolicyRoot 'source.bin'
    $sizePolicyOutputPath = Join-Path $sizePolicyRoot 'output.bin'
    [System.IO.File]::WriteAllBytes($sizePolicySourcePath, [byte[]](0..99))
    [System.IO.File]::WriteAllBytes($sizePolicyOutputPath, [byte[]](0..129))

    $overrideFallback = Test-MediaEncodeOutputSizePolicy `
        -SourcePath $sizePolicySourcePath `
        -OutputPath $sizePolicyOutputPath `
        -SizeGuardMode 'fallback_remux' `
        -MaxGrowthPercent 5 `
        -CompatibilityGrowthPercent 15 `
        -RouteReasonCode 'folder_policy_force_encode'
    Assert-Equal ([bool]$overrideFallback.Exceeded) $true 'Fallback-remux guard should detect oversized override-forced encode output.'
    Assert-Equal ([bool]$overrideFallback.Ok) $true 'Fallback-remux guard should let encode continue unless fallback succeeds.'
    Assert-Equal ([bool]$overrideFallback.ShouldBlock) $false 'Fallback-remux guard should not use strict publish block semantics.'
    Assert-Equal ([bool]$overrideFallback.ShouldFallbackRemux) $true 'Fallback-remux guard should request remux only for override-forced encodes.'
    Assert-Equal ([bool]$overrideFallback.Metadata.fallback_remux_eligible) $true 'Fallback-remux metadata should mark override-forced encode eligibility.'
    Assert-Equal ([bool]$overrideFallback.Metadata.should_fallback_remux) $true 'Fallback-remux metadata should record the requested fallback.'

    $nonOverrideFallback = Test-MediaEncodeOutputSizePolicy `
        -SourcePath $sizePolicySourcePath `
        -OutputPath $sizePolicyOutputPath `
        -SizeGuardMode 'fallback_remux' `
        -MaxGrowthPercent 5 `
        -CompatibilityGrowthPercent 15 `
        -RouteReasonCode 'bitrate_over_threshold'
    Assert-Equal ([bool]$nonOverrideFallback.Exceeded) $true 'Fallback-remux guard should still record non-override size growth.'
    Assert-Equal ([bool]$nonOverrideFallback.ShouldFallbackRemux) $false 'Fallback-remux guard should not request remux for non-override encodes.'
    Assert-Equal ([bool]$nonOverrideFallback.Metadata.fallback_remux_eligible) $false 'Fallback-remux metadata should mark non-override encodes ineligible.'
} finally {
    Remove-Item -LiteralPath $sizePolicyRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Assert-Equal (Get-MediaEncodeOutputMuxerName -OutputPath 'output.mkv') 'matroska' 'MKV encode output should keep Matroska muxer.'
Assert-Equal (Get-MediaEncodeOutputMuxerName -OutputPath 'output.mp4') 'mp4' 'MP4 encode output should use MP4 muxer when a route/video override selects MP4 output.'

Write-Host 'Media route selection checks passed.'
