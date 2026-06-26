# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline.ps1.
# Encode public wrapper.

function Do-Encode {
    param($file, [bool]$isTV, $tvInfo)

    return Invoke-MediaPipelineEncode -File $file -IsTV:$isTV -TvInfo $tvInfo
}
