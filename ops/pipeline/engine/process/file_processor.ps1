# ==============================================================================
# ops\pipeline\engine\process\file_processor.ps1
# ==============================================================================
# Extracted from ops\pipeline\entrypoints\MediaPipeline.ps1. The root entry script dot-sources
# this file to preserve the historical command and function surface.
# ==============================================================================

function Process-File {
    param(
        $file,
        [bool]$isTV,
        $idx,
        [int]$QueueIndex = 0,
        [int]$QueueTotal = 0,
        $PriorityInfo = $null,
        [string]$LibraryProfileId = ''
    )

    Invoke-MediaPipelineProcessFile -file $file -isTV:$isTV -idx $idx -QueueIndex $QueueIndex -QueueTotal $QueueTotal -PriorityInfo $PriorityInfo -LibraryProfileId $LibraryProfileId
}
