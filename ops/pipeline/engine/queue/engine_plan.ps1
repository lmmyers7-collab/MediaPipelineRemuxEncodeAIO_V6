# ==============================================================================
# ops\pipeline\engine\queue\engine_plan.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\queue\pipeline_engine.ps1. Keep function names stable;
# pipeline_engine.ps1 dot-sources this file as part of the queue engine surface.
# ==============================================================================

function New-MediaPipelineEnginePlan {
    param(
        [Parameter(Mandatory)] [string] $SourceMovies,
        [Parameter(Mandatory)] [string] $SourceTV,
        [Parameter(Mandatory)] [string] $QueueSnapshotPath,
        [bool] $Once = $false,
        [int] $SleepSeconds = 30,
        [string] $ScriptPath = '',
        [string] $ConfigPath = '',
        [string] $PowerShellPath = '',
        [string] $ParallelEncodeMode = 'single',
        [int] $MaxParallelEncodes = 1
    )

    return [pscustomobject]@{
        EnginePlanType     = 'media_pipeline_engine_plan.v1'
        SourceMovies       = $SourceMovies
        SourceTV           = $SourceTV
        QueueSnapshotPath   = $QueueSnapshotPath
        Once               = [bool]$Once
        SleepSeconds       = [int]$SleepSeconds
        ScriptPath         = $ScriptPath
        ConfigPath         = $ConfigPath
        PowerShellPath     = $PowerShellPath
        ParallelEncodeMode = $ParallelEncodeMode
        MaxParallelEncodes = [int]$MaxParallelEncodes
    }
}

function Get-MediaPipelineQueueEntryProgressValue {
    param(
        [Parameter(Mandatory)] $Entry,
        [Parameter(Mandatory)] [string] $RunProperty,
        [Parameter(Mandatory)] [string] $BucketProperty
    )

    $runValue = $null
    try {
        $runPropertyValue = $Entry.PSObject.Properties[$RunProperty]
        if ($runPropertyValue) { $runValue = [int]$runPropertyValue.Value }
    } catch {}
    if ($runValue -gt 0) { return [int]$runValue }

    try {
        $bucketPropertyValue = $Entry.PSObject.Properties[$BucketProperty]
        if ($bucketPropertyValue) { return [int]$bucketPropertyValue.Value }
    } catch {}
    return 0
}
