# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Encode publish handoff boundary module.

function Get-MediaPipelineEncodePublishBoundaryVersion {
    return 'encode_publish_boundary.v1'
}

function Complete-MediaPipelineEncodePublish {
    param([Parameter(Mandatory)] $Context)

    $file = $Context.File
    $localIn = $Context.LocalIn
    $paths = $Context.Paths
    $tempOut = $Context.TempOut
    $subResult = $Context.SubResult
    $usingCpu = [bool]$Context.UsingCpu
    $usingSafeRetry = [bool]$Context.UsingSafeRetry

    [System.IO.Directory]::CreateDirectory($paths.LocalDir) | Out-Null
    [System.IO.Directory]::CreateDirectory($paths.ServerDir) | Out-Null

    [System.IO.File]::Move($tempOut, $paths.LocalOut, $true)
    $Context.TempOut = $null

    Write-PlexCompatibilityReport -FilePath $paths.LocalOut -Context "ENCODE: "

    # CurrentRouteReasonCode/Reason and route_actions.video are already
    # synchronized at the point $usingCpu / $usingSafeRetry was set. The
    # locals below are derived for the publish call only; do not re-mutate
    # script-scope state here (see E1 / E3 fixes).
    $route = if ($usingCpu) { "encode-cpu-fallback" } elseif ($usingSafeRetry) { "encode-safe-retry" } else { "encode" }
    $routeReasonCode = [string]$script:CurrentRouteReasonCode
    $routeReason     = [string]$script:CurrentRouteReason
    $publishResult = Complete-PipelineOutputPublish -SourceFile $file -ScratchPath $localIn -Paths $paths -Route $route -ProgressRoute 'encode' -StagePrefix 'encode' -Context "ENCODE: " -RouteReasonCode $routeReasonCode -RouteReason $routeReason -Tx3gTracks @($subResult.Tx3gTracks) -BdpgsTracks @($subResult.BdpgsTracks) -VobSubTracks @($subResult.VobSubTracks) -ConvertedSrtSidecarCandidates @($subResult.ConvertedSrtSidecarCandidates) -SubtitleOutputReduction @($subResult.SubtitleOutputReduction)
    $script:LastPublishResult = $publishResult
    $Context.PublishResult = $publishResult
    if ($publishResult.DeleteLocalOutput) { $Context.PushOk = $true }
    if ($publishResult.KeepScratchInput) { $Context.LocalIn = $null }
    return New-MediaPipelineEncodeStageResult -Ok ([bool]$publishResult.Ok) -Terminal $true -Value ([bool]$publishResult.Ok) -Stage 'encode-publish'
}
