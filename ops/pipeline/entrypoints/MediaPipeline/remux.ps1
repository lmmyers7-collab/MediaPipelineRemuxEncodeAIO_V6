# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline.ps1.
# Public remux route wrapper.

function Do-Remux {
    param($file, [bool]$isTV, $tvInfo, [switch] $FallbackFromOversizedEncode, [switch] $FallbackFromDynamicHdrEncode)

    return Invoke-MediaPipelineRemux `
        -File $file `
        -IsTV:$isTV `
        -TvInfo $tvInfo `
        -FallbackFromOversizedEncode:([bool]$FallbackFromOversizedEncode) `
        -FallbackFromDynamicHdrEncode:([bool]$FallbackFromDynamicHdrEncode)
}
