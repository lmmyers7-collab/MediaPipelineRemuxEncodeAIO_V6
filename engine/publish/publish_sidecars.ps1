# Publish-sidecar helpers shared by publish orchestration.

function Publish-Tx3gSrtSidecarsFromPlan {
    param(
        [Parameter(Mandatory)] $Plan,
        [string] $Context = ''
    )
    $records = [System.Collections.Generic.List[object]]::new()
    $failures = [System.Collections.Generic.List[object]]::new()
    foreach ($failure in @($Plan.Failures)) {
        if ($failure) { $failures.Add($failure) }
    }
    foreach ($record in @($Plan.Tracks)) {
        if ($record -and [string]$record.status -eq 'existing') { $records.Add($record) }
    }
    foreach ($sidecar in @($Plan.SidecarFiles)) {
        if (-not $sidecar) { continue }
        $sourceSrt = [string]$sidecar.LocalPath
        $destination = [string]$sidecar.DestinationPath
        $streamIndex = if ($sidecar.Record -and $sidecar.Record.PSObject.Properties['stream_index']) { [int]$sidecar.Record.stream_index } else { -1 }
        if (Get-Command -Name Write-SubtitleTrackProgress -ErrorAction SilentlyContinue) {
            Write-SubtitleTrackProgress -Kind 'tx3g' -StreamIndex $streamIndex -Stage 'sidecar_write' -Status 'Writing TX3G SRT sidecar' -StepIndex 4 -StepTotal 4 -Detail (Split-Path -Leaf $destination)
        }
        $copy = Copy-SrtAtomic -SourcePath $sourceSrt -DestinationPath $destination
        if (-not $copy.Ok) {
            $entry = if ($sidecar.Record -and $sidecar.Record.PSObject.Properties['stream_index']) {
                @{ Stream = @{ index = $sidecar.Record.stream_index }; Lang = $sidecar.Record.language; Title = $sidecar.Record.title }
            } else {
                @{ Stream = @{ index = -1 }; Lang = ''; Title = '' }
            }
            $failure = New-Tx3gFailureRecord -Entry $entry -Reason $copy.Reason -ErrorCode $copy.ErrorCode
            $failures.Add($failure)
            if (Get-Command -Name Write-SubtitleTrackProgress -ErrorAction SilentlyContinue) {
                Write-SubtitleTrackProgress -Kind 'tx3g' -StreamIndex $streamIndex -Stage 'sidecar_write' -Status 'TX3G SRT sidecar write failed' -StepIndex 4 -StepTotal 4 -Detail $copy.Reason -Failed
            }
            Write-Log "${Context}TX3G->SRT: sidecar publish failed for $destination : $($copy.Reason)" "WARN"
            continue
        }
        if ($sidecar.Record) {
            if ($sidecar.Record.PSObject.Properties['status']) {
                $sidecar.Record.status = 'written'
            } else {
                Add-Member -InputObject $sidecar.Record -NotePropertyName 'status' -NotePropertyValue 'written' -Force
            }
            if ($sidecar.Record.PSObject.Properties['cue_count']) {
                $sidecar.Record.cue_count = $copy.CueCount
            } else {
                Add-Member -InputObject $sidecar.Record -NotePropertyName 'cue_count' -NotePropertyValue $copy.CueCount -Force
            }
            $records.Add($sidecar.Record)
        }
        if (Get-Command -Name Write-SubtitleTrackProgress -ErrorAction SilentlyContinue) {
            Write-SubtitleTrackProgress -Kind 'tx3g' -StreamIndex $streamIndex -Stage 'sidecar_write' -Status 'TX3G SRT sidecar written' -StepIndex 4 -StepTotal 4 -Detail (Split-Path -Leaf $destination) -CueCount $copy.CueCount -Completed
        }
        Write-Log "${Context}TX3G->SRT: sidecar written $(Split-Path -Leaf $destination)"
    }
    return @{
        Tracks   = @($records)
        Failures = @($failures)
    }
}
