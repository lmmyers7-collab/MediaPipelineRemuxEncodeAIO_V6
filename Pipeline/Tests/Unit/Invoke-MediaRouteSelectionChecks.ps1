param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
. (Join-Path $repoRoot 'engine\shared\media_constants.ps1')
. (Join-Path $repoRoot 'engine\decide\routing.ps1')
. (Join-Path $repoRoot 'engine\decide\encode_policy.ps1')

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

$movieThreshold = 8.0
$tvThreshold = 3.0
$movieBitrateThreshold = 35.0
$tvBitrateThreshold = 18.0

$inputs = @(
    @{
        Name = 'small 1080p low-bitrate'
        SizeBytes = [long](4 * 1GB)
        DurationSeconds = 7200.0
        Height = 1080
        ExpectedEstimatedMbps = [math]::Round((([double]([long](4 * 1GB)) * 8.0) / 7200.0) / 1000000.0, 3)
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
        ExpectedSizeOver = $true
        ExpectedBitrateOver = $true
        Expected = @{
            compatibility_advisory = @{ Route = 'encode'; ReasonCode = 'bitrate_over_threshold' }
            size = @{ Route = 'encode'; ReasonCode = 'size_over_threshold' }
            bitrate = @{ Route = 'encode'; ReasonCode = 'bitrate_over_threshold' }
            size_or_bitrate = @{ Route = 'encode'; ReasonCode = 'bitrate_over_threshold' }
        }
    }
)

foreach ($mode in @('compatibility_advisory','size','bitrate','size_or_bitrate')) {
    foreach ($inputCase in $inputs) {
        $plan = Resolve-MediaRouteBySize `
            -FileSizeBytes ([long]$inputCase.SizeBytes) `
            -IsTV:$false `
            -MovieThresholdGB $movieThreshold `
            -TVThresholdGB $tvThreshold `
            -DurationSeconds ([double]$inputCase.DurationSeconds) `
            -VideoCodec 'hevc' `
            -VideoHeight ([int]$inputCase.Height) `
            -RoutingProfile 'plex_direct_stream' `
            -RouteThresholdMode $mode `
            -MovieRouteMaxVideoBitrateMbps $movieBitrateThreshold `
            -TVRouteMaxVideoBitrateMbps $tvBitrateThreshold

        $expected = $inputCase.Expected[$mode]
        $label = "$mode / $($inputCase.Name)"
        Assert-Equal ([string]$plan.Route) ([string]$expected.Route) "$label route mismatch."
        Assert-Equal ([string]$plan.ReasonCode) ([string]$expected.ReasonCode) "$label reason code mismatch."
        Assert-Near ([double]$plan.EstimatedBitrateMbps) ([double]$inputCase.ExpectedEstimatedMbps) -Message "$label estimated bitrate mismatch."
        Assert-Near ([double]$plan.ThresholdGB) $movieThreshold -Message "$label size threshold mismatch."
        Assert-Near ([double]$plan.BitrateThresholdMbps) $movieBitrateThreshold -Message "$label bitrate threshold mismatch."
        Assert-Equal ([bool]$plan.SizeOverThreshold) ([bool]$inputCase.ExpectedSizeOver) "$label size-over-threshold mismatch."
        Assert-Equal ([bool]$plan.BitrateOverThreshold) ([bool]$inputCase.ExpectedBitrateOver) "$label bitrate-over-threshold mismatch."
        Assert-TraceContains -Plan $plan -Code 'routing_profile_selected' -Message "$label missing profile trace."
        Assert-TraceContains -Plan $plan -Code 'size_evaluated' -Message "$label missing size trace."
        Assert-TraceContains -Plan $plan -Code 'bitrate_estimated' -Message "$label missing bitrate trace."
        Assert-TraceContains -Plan $plan -Code ([string]$expected.ReasonCode) -Message "$label missing final reason trace."
    }
}

$h264FourK = Resolve-MediaRouteBySize `
    -FileSizeBytes ([long](4 * 1GB)) `
    -IsTV:$false `
    -MovieThresholdGB $movieThreshold `
    -TVThresholdGB $tvThreshold `
    -DurationSeconds 7200 `
    -VideoCodec 'h264' `
    -VideoHeight 2160 `
    -RoutingProfile 'plex_direct_stream' `
    -RouteThresholdMode 'compatibility_advisory' `
    -MovieRouteMaxVideoBitrateMbps $movieBitrateThreshold `
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
    -MovieThresholdGB $movieThreshold `
    -TVThresholdGB $tvThreshold `
    -DurationSeconds 900 `
    -VideoCodec 'h264' `
    -VideoHeight 1080 `
    -RoutingProfile 'plex_direct_stream' `
    -RouteThresholdMode 'size' `
    -MovieRouteMaxVideoBitrateMbps $movieBitrateThreshold `
    -H264RemuxMaxBitrateMbps 10
Assert-Equal ([string]$h264OverBitrateSizeOnly.Route) 'remux' 'H.264 over bitrate should still remux when size-only mode does not force encode.'
Assert-Equal ([string]$h264OverBitrateSizeOnly.ReasonCode) 'size_within_threshold' 'H.264 over bitrate in size-only mode should keep size route reason.'
Assert-Equal ([bool]$h264OverBitrateSizeOnly.BitrateOverThreshold) $true 'H.264 over bitrate evidence should still be exposed.'
Assert-TraceContains -Plan $h264OverBitrateSizeOnly -Code 'bitrate_threshold_ignored' -Message 'H.264 size-only route should trace ignored bitrate threshold.'

$missingDuration = Resolve-MediaRouteBySize `
    -FileSizeBytes ([long](4 * 1GB)) `
    -IsTV:$false `
    -MovieThresholdGB $movieThreshold `
    -TVThresholdGB $tvThreshold `
    -DurationSeconds 0 `
    -VideoCodec 'hevc' `
    -VideoHeight 1080 `
    -RoutingProfile 'plex_direct_stream' `
    -RouteThresholdMode 'bitrate' `
    -MovieRouteMaxVideoBitrateMbps $movieBitrateThreshold `
    -SourceMediaProfile @{ estimated_bitrate_mbps = 80.0; duration_seconds = 0 }
Assert-Equal ([string]$missingDuration.Route) 'remux' 'Missing duration should not force bitrate encode from source_media_profile estimated bitrate.'
Assert-Equal ([string]$missingDuration.ReasonCode) 'size_within_threshold' 'Missing duration should preserve size-within route reason.'
Assert-Near ([double]$missingDuration.EstimatedBitrateMbps) 0.0 -Message 'Missing duration should report zero route-estimated bitrate.'
Assert-Equal ([bool]$missingDuration.BitrateOverThreshold) $false 'Missing duration should not mark bitrate over threshold.'
Assert-True (-not ((Get-TraceCodes -Plan $missingDuration) -contains 'bitrate_over_threshold')) 'Missing duration unexpectedly fired bitrate_over_threshold.'
Assert-True (-not ((Get-TraceCodes -Plan $missingDuration) -contains 'bitrate_estimated')) 'Missing duration unexpectedly emitted bitrate_estimated trace.'

Assert-Equal (Get-MediaEncodeOutputMuxerName -OutputPath 'output.mkv') 'matroska' 'MKV encode output should keep Matroska muxer.'
Assert-Equal (Get-MediaEncodeOutputMuxerName -OutputPath 'output.mp4') 'mp4' 'MP4 encode output should use MP4 muxer when a route/video override selects MP4 output.'

Write-Host 'Media route selection checks passed.'
