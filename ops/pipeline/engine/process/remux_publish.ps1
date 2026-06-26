# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Remux publish handoff.

function Complete-MediaPipelineRemuxPublish {
    param([Parameter(Mandatory)] $Context)

    $publishResult = Complete-PipelineOutputPublish -SourceFile $Context.File -ScratchPath $Context.LocalIn -Paths $Context.Paths -Route 'remux' -ProgressRoute 'remux' -StagePrefix 'remux' -Context "REMUX: " -RouteReasonCode ([string]$script:CurrentRouteReasonCode) -RouteReason ([string]$script:CurrentRouteReason) -Tx3gTracks @($Context.SubTracks.Tx3gTracks) -BdpgsTracks @($Context.SubTracks.BdpgsTracks) -VobSubTracks @($Context.SubTracks.VobSubTracks) -ConvertedSrtSidecarCandidates @($Context.SubTracks.ConvertedSrtSidecarCandidates) -SubtitleOutputReduction @($Context.SubTracks.SubtitleOutputReduction)
    $script:LastPublishResult = $publishResult
    if ($publishResult.DeleteLocalOutput) { $Context.PushOk = $true }
    if ($publishResult.KeepScratchInput) { $Context.LocalIn = $null }
    return New-MediaPipelineRemuxStageResult -Ok ([bool]$publishResult.Ok) -Terminal $true -Value ([bool]$publishResult.Ok) -Stage 'remux-publish'
}
