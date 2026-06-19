param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSScriptRoot."
}

. (Join-Path $repoRoot 'ops\pipeline\engine\shared\media_constants.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\decide\routing.ps1')

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

$fallbackTrace = @(
    (New-MediaRouteDecisionTraceEntry -Code 'codec_remux_safe' -Message "codec 'h264' is remux-safe"),
    (New-MediaRouteDecisionTraceEntry -Code 'oversized_encode_remux_fallback' -Message 'Remux fallback after oversized encode; direct-copy size/bitrate caps bypassed for this fallback')
)
$fallbackPlan = New-MediaRoutePlan `
    -Route 'remux' `
    -ReasonCode 'oversized_encode_remux_fallback' `
    -Reason 'Remux fallback after oversized encode; direct-copy size/bitrate caps bypassed for this fallback' `
    -SourceCodec 'h264' `
    -SizeGB 4.0 `
    -ThresholdGB 3.0 `
    -EstimatedBitrateMbps 22.5 `
    -BitrateThresholdMbps 20.0 `
    -SizeOverThreshold:$true `
    -BitrateOverThreshold:$true `
    -PlexCompatibilityScore 95.0 `
    -RoutingProfile 'plex_direct_stream' `
    -RouteThresholdMode 'bitrate' `
    -SizeGuardMode 'fallback_remux' `
    -DecisionTrace @($fallbackTrace)

$script:CurrentRoutePlan = $fallbackPlan
$script:CurrentSizePolicyResult = [pscustomobject][ordered]@{
    mode = 'fallback_remux'
    routing_profile = 'plex_direct_stream'
    route_reason_code = 'bitrate_over_threshold'
    route_intent_reason_code = 'bitrate_over_threshold'
    max_growth_percent = 10.0
    limit_ratio = 1.10
    source_size_bytes = 100L
    output_size_bytes = 130L
    ratio = 1.30
    exceeded = $true
    enforced = $true
    forced_route_override = $false
    fallback_remux_eligible = $true
    should_fallback_remux = $true
    message = 'encoded output is 1.30x source; exceeds 1.10x limit; fallback remux will be attempted because encode was an automatic size/bitrate threshold decision'
}

$routeMetadata = Get-ActiveMediaRoutePlanMetadata
$routeMap = [ordered]@{}
Add-MediaRoutePlanMetadataToMap -Map $routeMap -Metadata $routeMetadata | Out-Null
Assert-True ($routeMap.Contains('route_explanation')) 'Route metadata map should expose compact route_explanation output evidence.'
Assert-Equal ([string]$routeMap['route_explanation'].schema_version) 'route_explanation.v1' 'Route explanation schema version mismatch.'
Assert-Equal ([bool]$routeMap['route_explanation'].remux_fallback['accepted']) $true 'Route explanation should mark accepted fallback remux.'
Assert-Equal ([string]$routeMap['route_explanation'].remux_fallback['codec_gate_code']) 'codec_remux_safe' 'Route explanation should expose accepted remux codec gate.'
Assert-Equal ([bool]$routeMap['route_explanation'].remux_fallback['direct_copy_size_bitrate_caps_bypassed']) $true 'Fallback explanation should mark size/bitrate cap bypass evidence.'
Assert-True ((@($routeMap['route_explanation'].decision_summary) -join ' ') -match 'remux fallback accepted') 'Route explanation should summarize accepted fallback remux.'

$advisoryMetadata = [pscustomobject][ordered]@{
    route = 'encode'
    route_reason_code = 'bitrate_over_threshold'
    route_reason = 'bitrate above threshold'
    size_gb = 4.0
    threshold_gb = 3.0
    estimated_bitrate_mbps = 22.5
    bitrate_threshold_mbps = 20.0
    size_over_threshold = $true
    bitrate_over_threshold = $true
    plex_compatibility_score = 80.0
    routing_profile = 'plex_direct_stream'
    route_threshold_mode = 'bitrate'
    size_guard_mode = 'advisory'
    source_codec = 'h264'
    decision_trace = @((New-MediaRouteDecisionTraceEntry -Code 'bitrate_over_threshold' -Message 'bitrate above threshold'))
    size_policy = [pscustomobject][ordered]@{
        mode = 'advisory'
        routing_profile = 'plex_direct_stream'
        route_reason_code = 'bitrate_over_threshold'
        route_intent_reason_code = 'bitrate_over_threshold'
        max_growth_percent = 10.0
        limit_ratio = 1.10
        source_size_bytes = 100L
        output_size_bytes = 130L
        ratio = 1.30
        exceeded = $true
        enforced = $false
        forced_route_override = $false
        fallback_remux_eligible = $true
        should_fallback_remux = $false
        message = 'encoded output is 1.30x source; exceeds 1.10x limit'
    }
}
$advisoryExplanation = New-MediaRouteExplanation -Metadata $advisoryMetadata
Assert-Equal ([bool]$advisoryExplanation.remux_fallback['attempted']) $false 'Advisory size guard should explain that fallback remux was not attempted.'
Assert-Equal ([string]$advisoryExplanation.remux_fallback['blocked_reason_code']) 'size_guard_mode_not_fallback_remux' 'Advisory size guard should name why fallback remux was not attempted.'
Assert-True ((@($advisoryExplanation.operator_notes) -join ' ') -match 'SizeGuardMode advisory warns and publishes') 'Advisory route explanation should tell the operator why oversized output published.'

Write-Host 'Route explanation evidence checks passed.'
