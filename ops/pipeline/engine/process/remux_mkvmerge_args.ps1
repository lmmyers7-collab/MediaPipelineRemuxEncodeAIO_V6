# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Remux mkvmerge command argument construction.

function New-MediaPipelineRemuxMkvmergeArgumentList {
    param([Parameter(Mandatory)] $Context)

    [System.IO.Directory]::CreateDirectory($Context.Paths.LocalDir) | Out-Null
    [System.IO.Directory]::CreateDirectory($Context.Paths.ServerDir) | Out-Null

    if (-not (Test-EstimatedOutputSpace -SourcePath $Context.LocalIn -Label "REMUX-MUX" -RemuxFinalStage)) {
        $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.LocalIn -Classification 'transient' -Reason 'Insufficient scratch space for mkvmerge final mux' -Stage 'remux-mkvmerge' -ErrorCode 'REMUX_INSUFFICIENT_SPACE' -SuggestedAction 'Free space on the scratch volume or move LocalBase to a larger disk before retrying. The temp_av file is still consuming source-equivalent space and mkvmerge needs room for the final output.'
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-mkvmerge'
    }

    $mkvArgs = [System.Collections.Generic.List[string]]::new()
    $sourceTitle = Get-SourceTitleTag -FilePath $Context.LocalIn
    $effectiveTitle = if (-not [string]::IsNullOrWhiteSpace($sourceTitle)) {
        Write-Log "REMUX: preserving source title '$sourceTitle'" "DEBUG"
        $sourceTitle
    } else {
        "Encoded by MediaPipeline $($script:ProductVersion) (pipeline $($script:PipelineVersion))"
    }
    $mkvArgs.AddRange([string[]]@(
        "--output", $Context.Paths.LocalOut,
        "--title",  $effectiveTitle
    ))

    $audioTids = @(Get-MkvmergeAudioTids -FilePath $Context.TempAvFile -Context "REMUX: ")
    if ($script:LastAudioTrackCount -gt 0 -and $audioTids.Count -ge $script:LastAudioTrackCount) {
        for ($aIdx = 0; $aIdx -lt $script:LastAudioTrackCount; $aIdx++) {
            $tid = [int]$audioTids[$aIdx]
            $isDefault = if ($aIdx -eq $script:LastAudioDefaultIndex) { 'yes' } else { 'no' }
            $mkvArgs.AddRange([string[]]@("--default-track", "$($tid):$isDefault"))
        }
    } elseif ($script:LastAudioTrackCount -gt 0) {
        $reason = "REMUX: probed $($audioTids.Count) audio TIDs in temp_av but expected $($script:LastAudioTrackCount); refusing to mux with ambiguous audio default-track flags"
        Write-Log $reason "ERROR"
        $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.LocalIn -Classification 'transient' -Reason $reason -Stage 'remux-audio-default-track' -ErrorCode 'REMUX_AUDIO_TID_MAPPING_FAILED' -SuggestedAction 'Inspect temp AV stream layout and mkvmerge track-ID probing before retrying; the output was not published with ambiguous default audio flags.'
        $Context.LocalIn = $null
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-audio-default-track'
    }
    $mkvArgs.Add($Context.TempAvFile)
    if ($Context.SubTracks.SourceTracks.Count -gt 0) {
        foreach ($track in $Context.SubTracks.SourceTracks) {
            $mkvArgs.AddRange([string[]]@(
                "--language",      "$($track.MkvTid):$($track.Lang)",
                "--track-name",    "$($track.MkvTid):$($track.Title)",
                "--default-track", "$($track.MkvTid):$(if ($track.IsDefault) { 'yes' } else { 'no' })"
            ))
            if ($track.IsForced) {
                $mkvArgs.AddRange([string[]]@("--forced-track", "$($track.MkvTid):yes"))
            }
        }
        $mkvArgs.AddRange([string[]]@("--no-video","--no-audio","--subtitle-tracks",
            (($Context.SubTracks.SourceTracks | ForEach-Object { $_.MkvTid }) -join ","),$Context.LocalIn))
    }
    foreach ($srt in $Context.SubTracks.ExternalTracks) {
        if (-not $srt.SrtPath) { continue }
        $mkvArgs.AddRange([string[]]@("--language","0:$($srt.Lang)","--track-name","0:$($srt.Title)",
            "--default-track","0:$(if ($srt.IsDefault) { 'yes' } else { 'no' })"))
        if ($srt.IsForced) { $mkvArgs.AddRange([string[]]@("--forced-track","0:yes")) }
        $mkvArgs.Add($srt.SrtPath)
    }

    $Context.MkvArgs = @($mkvArgs.ToArray())
    return New-MediaPipelineRemuxStageResult -Ok $true -Terminal $false -Stage 'remux-mkvmerge-args'
}
