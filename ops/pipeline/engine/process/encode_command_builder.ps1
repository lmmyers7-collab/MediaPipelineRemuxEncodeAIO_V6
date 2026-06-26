# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Encode core command argument handoff.

function Get-MediaPipelineEncodeCommandArgumentList {
    param([Parameter(Mandatory)] $Plan)

    return @($Plan.ArgumentList)
}
