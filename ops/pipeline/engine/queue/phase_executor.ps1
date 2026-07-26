# ==============================================================================
# ops\pipeline\engine\queue\phase_executor.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\queue\pipeline_engine.ps1. Keep function names stable;
# pipeline_engine.ps1 dot-sources this file as part of the queue engine surface.
# ==============================================================================

function Invoke-MediaPipelineProcessQueueEntry {
    param(
        [Parameter(Mandatory)] $Entry,
        [Parameter(Mandatory)] $ProcessedIndex
    )

    $progressQueueIndex = Get-MediaPipelineQueueEntryProgressValue -Entry $Entry -RunProperty 'RunQueueIndex' -BucketProperty 'QueueIndex'
    $progressQueueTotal = Get-MediaPipelineQueueEntryProgressValue -Entry $Entry -RunProperty 'RunQueueTotal' -BucketProperty 'QueueTotal'
    return Process-File $Entry.File ([bool]$Entry.IsTV) $ProcessedIndex -QueueIndex $progressQueueIndex -QueueTotal $progressQueueTotal -PriorityInfo $Entry.PriorityInfo -LibraryProfileId ([string]$Entry.LibraryId)
}

function Get-MediaPipelineRunMonitorResultValue {
    param($Object, [Parameter(Mandatory)] [string] $Name, $Default = $null)
    if ($null -eq $Object) { return $Default }
    if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($Name)) { return $Object[$Name] }
    $property = $Object.PSObject.Properties[$Name]
    if ($property -and $null -ne $property.Value) { return $property.Value }
    return $Default
}

function Get-MediaPipelineRunMonitorFirstResultValue {
    param(
        $Object,
        [Parameter(Mandatory)] [string[]] $Names,
        $Default = $null
    )
    foreach ($name in $Names) {
        $value = Get-MediaPipelineRunMonitorResultValue -Object $Object -Name $name -Default $null
        if ($null -ne $value) { return $value }
    }
    return $Default
}

function Resolve-MediaPipelineRunMonitorTerminalArtifact {
    param(
        [Parameter(Mandatory)]
        [ValidateSet('completed','parked','failed','blocked','review','skipped','stopped')]
        [string] $Lifecycle,
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [string] $PipelineSidecarPath = '',
        [string] $ManifestPath = '',
        [string] $FailureArtifactPath = ''
    )

    $kind = ''
    $source = ''
    $path = ''
    $expectedSchema = ''
    $runField = ''
    $routeField = ''
    $reasonField = ''
    $reasonCodeField = ''
    switch ($Lifecycle) {
        'completed' {
            $kind = 'completed'; $source = 'completed_sidecar'; $path = $PipelineSidecarPath
            $expectedSchema = 'pipeline_sidecar.v1'; $runField = 'correlation_id'
            $routeField = 'route'; $reasonField = 'route_reason'; $reasonCodeField = 'route_reason_code'
        }
        'parked' {
            $kind = 'pending_publish'; $source = 'pending_publish_manifest'; $path = $ManifestPath
            $expectedSchema = 'pending_push_manifest.v1'; $runField = 'run_id'
            $routeField = 'route'; $reasonField = 'route_reason'; $reasonCodeField = 'route_reason_code'
        }
        { $_ -in @('failed','blocked','review') } {
            $kind = if ($Lifecycle -eq 'review') { 'review' } else { 'failure' }
            $source = 'failure_artifact'; $path = $FailureArtifactPath
            $expectedSchema = 'failure_record.v1'; $runField = 'correlation_id'
            $routeField = 'final_route'; $reasonField = 'final_reason'; $reasonCodeField = 'final_reason_code'
        }
        default {
            return [pscustomobject]@{
                Verified = $false; Kind = ''; EvidenceSource = ''; ArtifactPath = ''; Route = ''
                Reason = ''; ReasonCode = 'terminal_artifact_not_applicable'; PublishedPath = ''
                ParkedPath = ''; IntendedFinalPath = ''; SidecarPaths = @(); NextAction = ''; Payload = $null
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace($path) -or -not (Test-Path -LiteralPath $path -PathType Leaf -ErrorAction SilentlyContinue)) {
        return [pscustomobject]@{
            Verified = $false; Kind = $kind; EvidenceSource = $source; ArtifactPath = $path; Route = ''
            Reason = 'The expected terminal evidence artifact is unavailable.'; ReasonCode = 'terminal_artifact_unavailable'
            PublishedPath = ''; ParkedPath = ''; IntendedFinalPath = ''; SidecarPaths = @(); NextAction = ''; Payload = $null
        }
    }

    try {
        $payload = Get-Content -LiteralPath $path -Raw -ErrorAction Stop | ConvertFrom-Json -Depth 40 -ErrorAction Stop
    } catch {
        return [pscustomobject]@{
            Verified = $false; Kind = $kind; EvidenceSource = $source; ArtifactPath = $path; Route = ''
            Reason = 'The terminal evidence artifact could not be parsed.'; ReasonCode = 'terminal_artifact_invalid'
            PublishedPath = ''; ParkedPath = ''; IntendedFinalPath = ''; SidecarPaths = @(); NextAction = ''; Payload = $null
        }
    }

    $schema = [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $payload -Names @('schema_version','SchemaVersion') -Default '')
    $artifactRunId = [string](Get-MediaPipelineRunMonitorResultValue -Object $payload -Name $runField -Default '')
    $artifactJobId = [string](Get-MediaPipelineRunMonitorResultValue -Object $payload -Name 'run_monitor_job_id' -Default '')
    if ($schema -ne $expectedSchema) {
        return [pscustomobject]@{
            Verified = $false; Kind = $kind; EvidenceSource = $source; ArtifactPath = $path; Route = ''
            Reason = "Terminal artifact schema '$schema' is not '$expectedSchema'."; ReasonCode = 'terminal_artifact_schema_mismatch'
            PublishedPath = ''; ParkedPath = ''; IntendedFinalPath = ''; SidecarPaths = @(); NextAction = ''; Payload = $payload
        }
    }
    if (-not [string]::Equals($artifactRunId, $RunId, [System.StringComparison]::Ordinal) -or
        -not [string]::Equals($artifactJobId, $JobId, [System.StringComparison]::Ordinal)) {
        return [pscustomobject]@{
            Verified = $false; Kind = $kind; EvidenceSource = $source; ArtifactPath = $path; Route = ''
            Reason = 'Terminal artifact run/job identity does not match the accepted monitor item.'
            ReasonCode = 'terminal_artifact_correlation_mismatch'; PublishedPath = ''; ParkedPath = ''
            IntendedFinalPath = ''; SidecarPaths = @(); NextAction = ''; Payload = $payload
        }
    }

    $reason = [string](Get-MediaPipelineRunMonitorResultValue -Object $payload -Name $reasonField -Default '')
    $reasonCode = [string](Get-MediaPipelineRunMonitorResultValue -Object $payload -Name $reasonCodeField -Default '')
    if ($Lifecycle -in @('failed','blocked','review')) {
        if ([string]::IsNullOrWhiteSpace($reason)) {
            $reason = [string](Get-MediaPipelineRunMonitorResultValue -Object $payload -Name 'reason' -Default '')
        }
        if ([string]::IsNullOrWhiteSpace($reasonCode)) {
            $reasonCode = [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $payload -Names @('error_code','ErrorCode') -Default '')
        }
    }
    $artifactSidecarPaths = [System.Collections.Generic.List[string]]::new()
    if ($Lifecycle -eq 'completed') {
        foreach ($sidecarPath in @(Get-MediaPipelineRunMonitorResultValue -Object $payload -Name 'sidecar_paths' -Default @())) {
            $sidecarText = [string]$sidecarPath
            if (-not [string]::IsNullOrWhiteSpace($sidecarText)) { $artifactSidecarPaths.Add($sidecarText) | Out-Null }
        }
    } elseif ($Lifecycle -eq 'parked') {
        foreach ($sidecarEntry in @(Get-MediaPipelineRunMonitorResultValue -Object $payload -Name 'sidecar_files' -Default @())) {
            $sidecarText = if ($sidecarEntry -is [string]) {
                [string]$sidecarEntry
            } else {
                [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $sidecarEntry -Names @('local_file','LocalFile') -Default '')
            }
            if (-not [string]::IsNullOrWhiteSpace($sidecarText)) { $artifactSidecarPaths.Add($sidecarText) | Out-Null }
        }
    }
    return [pscustomobject]@{
        Verified = $true
        Kind = $kind
        EvidenceSource = $source
        ArtifactPath = $path
        Route = [string](Get-MediaPipelineRunMonitorResultValue -Object $payload -Name $routeField -Default '')
        Reason = $reason
        ReasonCode = $reasonCode
        PublishedPath = if ($Lifecycle -eq 'completed') { [string](Get-MediaPipelineRunMonitorResultValue -Object $payload -Name 'output_path' -Default '') } else { '' }
        ParkedPath = if ($Lifecycle -eq 'parked') { [string](Get-MediaPipelineRunMonitorResultValue -Object $payload -Name 'local_file' -Default '') } else { '' }
        IntendedFinalPath = if ($Lifecycle -eq 'parked') {
            [string](Get-MediaPipelineRunMonitorResultValue -Object $payload -Name 'server_out' -Default '')
        } elseif ($Lifecycle -eq 'completed') {
            [string](Get-MediaPipelineRunMonitorResultValue -Object $payload -Name 'output_path' -Default '')
        } else { '' }
        SidecarPaths = @($artifactSidecarPaths.ToArray())
        NextAction = [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $payload -Names @('suggested_action','operator_action','SuggestedAction') -Default '')
        Payload = $payload
    }
}

function Get-MediaPipelineRunMonitorTerminalTrackAction {
    param([Parameter(Mandatory)] $Record)

    foreach ($name in @('planned_action','PlannedAction','action','Action')) {
        $candidate = [string](Get-MediaPipelineRunMonitorResultValue -Object $Record -Name $name -Default '')
        if (-not [string]::IsNullOrWhiteSpace($candidate)) {
            return $candidate.Trim().ToLowerInvariant()
        }
    }
    return ''
}

function Resolve-MediaPipelineRunMonitorTerminalAudioAction {
    param([string] $Action = '')

    switch ($Action) {
        'not_applicable' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'not_applicable'; State = 'not_applicable' } }
        'omit_all' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'not_applicable'; State = 'not_applicable' } }
        'passthrough' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'passthrough'; State = 'completed' } }
        'copy' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'passthrough'; State = 'completed' } }
        'transcode' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'transcode'; State = 'completed' } }
        'transcode_downmix' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'transcode_downmix'; State = 'completed' } }
        'drop' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'drop'; State = 'dropped' } }
        default { return [pscustomobject]@{ Recognized = $false; CurrentAction = 'unknown'; State = 'unknown' } }
    }
}

function Resolve-MediaPipelineRunMonitorTerminalSubtitleAction {
    param(
        [string] $Action = '',
        [switch] $RoutesToReview
    )

    if ($RoutesToReview) {
        return [pscustomobject]@{ Recognized = $true; CurrentAction = 'review'; State = 'review' }
    }
    switch ($Action) {
        'preserve_original' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'preserve_original'; State = 'completed' } }
        'keep' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'preserve_original'; State = 'completed' } }
        'convert_ass_to_srt' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'convert_ass_to_srt'; State = 'completed' } }
        'convertass' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'convert_ass_to_srt'; State = 'completed' } }
        'convert_tx3g_to_srt' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'convert_tx3g_to_srt'; State = 'completed' } }
        'converttx3g' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'convert_tx3g_to_srt'; State = 'completed' } }
        'ocr_bdpgs_to_srt' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'ocr_bdpgs_to_srt'; State = 'completed' } }
        'convertbdpgs' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'ocr_bdpgs_to_srt'; State = 'completed' } }
        'ocr_vobsub_to_srt' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'ocr_vobsub_to_srt'; State = 'completed' } }
        'convertvobsub' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'ocr_vobsub_to_srt'; State = 'completed' } }
        'burn_in' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'burn_in'; State = 'completed' } }
        'burn' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'burn_in'; State = 'completed' } }
        'drop' { return [pscustomobject]@{ Recognized = $true; CurrentAction = 'drop'; State = 'dropped' } }
        default { return [pscustomobject]@{ Recognized = $false; CurrentAction = 'unknown'; State = 'unknown' } }
    }
}

function Sync-MediaPipelineRunMonitorTerminalTracks {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [Parameter(Mandatory)] $TerminalProof
    )

    if (-not [bool]$TerminalProof.Verified -or $null -eq $TerminalProof.Payload -or
        -not (Get-Command -Name Set-MediaPipelineRunMonitorTrackProgress -ErrorAction SilentlyContinue)) {
        return
    }

    $evidenceSource = [string]$TerminalProof.EvidenceSource
    $payload = $TerminalProof.Payload
    $audioRecords = @(Get-MediaPipelineRunMonitorResultValue -Object $payload -Name 'audio_decisions' -Default @())
    # Apply recognized results first and fail-closed results last. The track
    # updater also authors aggregate provenance, so this makes an unresolved
    # collection remain unknown regardless of artifact record order.
    foreach ($recognizedPass in @($true, $false)) {
      foreach ($record in $audioRecords) {
        if ($null -eq $record) { continue }
        $trackId = [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $record -Names @('track_id','TrackId') -Default '')
        $streamIndexValue = Get-MediaPipelineRunMonitorFirstResultValue -Object $record -Names @('source_stream_index','SourceStreamIndex') -Default $null
        if ([string]::IsNullOrWhiteSpace($trackId) -and $null -ne $streamIndexValue -and [int]$streamIndexValue -ge 0) {
            $trackId = "audio:$([int]$streamIndexValue)"
        }
        if ([string]::IsNullOrWhiteSpace($trackId)) { continue }

        $action = Get-MediaPipelineRunMonitorTerminalTrackAction -Record $record
        $terminalAction = Resolve-MediaPipelineRunMonitorTerminalAudioAction -Action $action
        if ([bool]$terminalAction.Recognized -ne [bool]$recognizedPass) { continue }
        $currentAction = [string]$terminalAction.CurrentAction
        $trackState = [string]$terminalAction.State
        $evidenceProvenance = if ([bool]$terminalAction.Recognized) { 'terminal' } else { 'unknown' }
        $reason = [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $record -Names @('reason','Reason') -Default '')
        $reasonCode = [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $record -Names @('reason_code','ReasonCode') -Default '')
        if (-not [bool]$terminalAction.Recognized -and [string]::IsNullOrWhiteSpace($reasonCode)) {
            $reasonCode = if ([string]::IsNullOrWhiteSpace($action)) { 'terminal_audio_action_missing' } else { 'terminal_audio_action_unsupported' }
        }
        $outputCodec = if ([bool]$terminalAction.Recognized) { [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $record -Names @('output_codec','OutputCodec') -Default '') } else { '' }
        $outputChannels = if ([bool]$terminalAction.Recognized) { Get-MediaPipelineRunMonitorFirstResultValue -Object $record -Names @('output_channels','OutputChannels') -Default $null } else { $null }
        $outputLayout = if ([bool]$terminalAction.Recognized) { [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $record -Names @('output_layout','OutputLayout','ChannelLayout') -Default '') } else { '' }
        $isDefault = if ([bool]$terminalAction.Recognized) { Get-MediaPipelineRunMonitorFirstResultValue -Object $record -Names @('is_default','IsDefault') -Default $null } else { $null }
        $result = if (-not [bool]$terminalAction.Recognized) {
            if ([string]::IsNullOrWhiteSpace($action)) { 'Terminal audio evidence did not identify an action.' } else { "Unsupported terminal audio action '$action' was suppressed." }
        } elseif (-not [string]::IsNullOrWhiteSpace($reason)) { $reason } else { $currentAction }
        Set-MediaPipelineRunMonitorTrackProgress `
            -Kind audio `
            -RunId $RunId `
            -JobId $JobId `
            -TrackId $trackId `
            -CurrentAction $currentAction `
            -State $trackState `
            -Result $result `
            -Reason $reason `
            -ReasonCode $reasonCode `
            -OutputCodec $outputCodec `
            -OutputChannels $outputChannels `
            -OutputLayout $outputLayout `
            -IsDefault $isDefault `
            -EvidenceSource $evidenceSource `
            -EvidenceProvenance $evidenceProvenance | Out-Null
      }
    }

    $conversionByTrack = @{}
    foreach ($conversion in @(Get-MediaPipelineRunMonitorResultValue -Object $payload -Name 'subtitle_conversion_results' -Default @())) {
        if ($null -eq $conversion) { continue }
        $conversionTrackId = [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $conversion -Names @('track_id','TrackId') -Default '')
        if (-not [string]::IsNullOrWhiteSpace($conversionTrackId)) { $conversionByTrack[$conversionTrackId] = $conversion }
    }
    $subtitleRecords = @(Get-MediaPipelineRunMonitorResultValue -Object $payload -Name 'subtitle_decisions' -Default @())
    foreach ($recognizedPass in @($true, $false)) {
      foreach ($record in $subtitleRecords) {
        if ($null -eq $record) { continue }
        $trackId = [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $record -Names @('track_id','TrackId') -Default '')
        if ([string]::IsNullOrWhiteSpace($trackId)) {
            # Compatibility is deliberately fail-closed: older terminal artifacts
            # without the durable track identity cannot prove a per-track result.
            continue
        }
        $conversion = if ($conversionByTrack.ContainsKey($trackId)) { $conversionByTrack[$trackId] } else { $null }
        $action = Get-MediaPipelineRunMonitorTerminalTrackAction -Record $record
        $routesToReview = [bool](Get-MediaPipelineRunMonitorFirstResultValue -Object $record -Names @('routes_to_review','RoutesToReview') -Default $false)
        $terminalAction = Resolve-MediaPipelineRunMonitorTerminalSubtitleAction -Action $action -RoutesToReview:$routesToReview
        if ([bool]$terminalAction.Recognized -ne [bool]$recognizedPass) { continue }
        $currentAction = [string]$terminalAction.CurrentAction
        $trackState = [string]$terminalAction.State
        $evidenceProvenance = if ([bool]$terminalAction.Recognized) { 'terminal' } else { 'unknown' }
        $reason = [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $record -Names @('review_reason','ReviewReason','reason','Reason','policy_reason','PolicyReason') -Default '')
        $reasonCode = [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $record -Names @('review_error_code','ReviewErrorCode','reason_code','ReasonCode') -Default '')
        if (-not [bool]$terminalAction.Recognized -and [string]::IsNullOrWhiteSpace($reasonCode)) {
            $reasonCode = if ([string]::IsNullOrWhiteSpace($action)) { 'terminal_subtitle_action_missing' } else { 'terminal_subtitle_action_unsupported' }
        }
        $outputCodec = if ([bool]$terminalAction.Recognized) { [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $conversion -Names @('output_codec','OutputCodec','output_subtitle_kind') -Default (Get-MediaPipelineRunMonitorFirstResultValue -Object $record -Names @('output_codec','OutputCodec') -Default '')) } else { '' }
        $outputLocation = if ([bool]$terminalAction.Recognized) { [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $conversion -Names @('output_location','OutputLocation','expected_output_location') -Default (Get-MediaPipelineRunMonitorFirstResultValue -Object $record -Names @('output_location','OutputLocation') -Default '')) } else { '' }
        if ($outputLocation -notin @('embedded','external_sidecar','burned_into_video','dropped','not_applicable','unknown')) { $outputLocation = '' }
        $outputPath = if ([bool]$terminalAction.Recognized) { [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $conversion -Names @('output_path','OutputPath') -Default '') } else { '' }
        $parkedPath = if ([bool]$terminalAction.Recognized) { [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $conversion -Names @('parked_path','ParkedPath') -Default '') } else { '' }
        $intendedFinalPath = if ([bool]$terminalAction.Recognized) { [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $conversion -Names @('intended_final_path','IntendedFinalPath') -Default '') } else { '' }
        $result = [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $conversion -Names @('result','Result','action') -Default '')
        if (-not [bool]$terminalAction.Recognized) {
            $result = if ([string]::IsNullOrWhiteSpace($action)) { 'Terminal subtitle evidence did not identify an action.' } else { "Unsupported terminal subtitle action '$action' was suppressed." }
        } elseif ([string]::IsNullOrWhiteSpace($result)) {
            $result = if (-not [string]::IsNullOrWhiteSpace($reason)) { $reason } else { $currentAction }
        }
        Set-MediaPipelineRunMonitorTrackProgress `
            -Kind subtitles `
            -RunId $RunId `
            -JobId $JobId `
            -TrackId $trackId `
            -CurrentAction $currentAction `
            -State $trackState `
            -Result $result `
            -Reason $reason `
            -ReasonCode $reasonCode `
            -OutputCodec $outputCodec `
            -OutputLocation $outputLocation `
            -OutputPath $outputPath `
            -ParkedPath $parkedPath `
            -IntendedFinalPath $intendedFinalPath `
            -EvidenceSource $evidenceSource `
            -EvidenceProvenance $evidenceProvenance | Out-Null
      }
    }
    if (Get-Command -Name Complete-MediaPipelineRunMonitorTrackStageFromEvidence -ErrorAction SilentlyContinue) {
        Complete-MediaPipelineRunMonitorTrackStageFromEvidence -Kind audio -RunId $RunId -JobId $JobId -EvidenceSource $evidenceSource | Out-Null
        Complete-MediaPipelineRunMonitorTrackStageFromEvidence -Kind subtitles -RunId $RunId -JobId $JobId -EvidenceSource $evidenceSource | Out-Null
    }
}

function Start-MediaPipelineRunMonitorQueueEntry {
    param([Parameter(Mandatory)] $Entry)

    $jobId = [string]$Entry.RunMonitorJobId
    if ([string]::IsNullOrWhiteSpace($jobId) -or
        [string]::IsNullOrWhiteSpace([string]$script:PipelineRunId) -or
        -not (Get-Command -Name Set-MediaPipelineRunMonitorItemLifecycle -ErrorAction SilentlyContinue)) {
        return
    }
    Set-MediaPipelineRunMonitorItemLifecycle -RunId ([string]$script:PipelineRunId) -JobId $jobId -State 'active' -NextAction 'Monitor backend-authored stage evidence.' | Out-Null
    Set-MediaPipelineRunMonitorStage -RunId ([string]$script:PipelineRunId) -JobId $jobId -StageId 'accepted' -State 'completed' -Detail 'Accepted into the fingerprinted Backend Queue Run Once workload.' -EvidenceSource 'queue_plan_acceptance' | Out-Null
    Set-MediaPipelineRunMonitorStage -RunId ([string]$script:PipelineRunId) -JobId $jobId -StageId 'source_discovery' -State 'completed' -Detail 'Source discovery and Queue preflight completed before accepted membership was frozen.' -EvidenceSource 'queue_discovery' | Out-Null
}

function Complete-MediaPipelineRunMonitorQueueEntry {
    param(
        [Parameter(Mandatory)] $Entry,
        [Parameter(Mandatory)] $Result
    )

    $jobId = [string]$Entry.RunMonitorJobId
    $runId = [string]$script:PipelineRunId
    if ([string]::IsNullOrWhiteSpace($jobId) -or [string]::IsNullOrWhiteSpace($runId) -or
        -not (Get-Command -Name Set-MediaPipelineRunMonitorItemLifecycle -ErrorAction SilentlyContinue)) {
        return
    }

    $status = ([string]$Result.Status).Trim().ToLowerInvariant()
    $publishState = ([string]$Result.PublishState).Trim().ToLowerInvariant()
    $reason = [string]$Result.Reason
    $reasonCode = [string]$Result.ErrorCode
    $retryable = if ($Result.PSObject.Properties['Retryable']) { [bool]$Result.Retryable } else { $null }
    $publishEvidence = Get-MediaPipelineRunMonitorResultValue -Object $Result -Name 'PublishEvidence' -Default $null
    $publishedPath = [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $Result -Names @('PublishedPath','published_path') -Default (Get-MediaPipelineRunMonitorFirstResultValue -Object $publishEvidence -Names @('published_path','PublishedPath') -Default ''))
    $parkedPath = [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $Result -Names @('ParkedPath','parked_path') -Default (Get-MediaPipelineRunMonitorFirstResultValue -Object $publishEvidence -Names @('parked_path','ParkedPath') -Default ''))
    $intendedFinalPath = [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $Result -Names @('IntendedFinalPath','intended_final_path') -Default (Get-MediaPipelineRunMonitorFirstResultValue -Object $publishEvidence -Names @('intended_final_path','IntendedFinalPath') -Default ''))
    $manifestPath = [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $Result -Names @('ManifestPath','manifest_path') -Default (Get-MediaPipelineRunMonitorFirstResultValue -Object $publishEvidence -Names @('manifest_path','ManifestPath') -Default ''))
    $pipelineSidecarPath = [string](Get-MediaPipelineRunMonitorFirstResultValue -Object $Result -Names @('PipelineSidecarPath','pipeline_sidecar_path') -Default (Get-MediaPipelineRunMonitorFirstResultValue -Object $publishEvidence -Names @('pipeline_sidecar_path','PipelineSidecarPath') -Default ''))
    $sidecarPaths = @(Get-MediaPipelineRunMonitorFirstResultValue -Object $Result -Names @('SidecarPaths','sidecar_paths') -Default (Get-MediaPipelineRunMonitorFirstResultValue -Object $publishEvidence -Names @('sidecar_paths','SidecarPaths') -Default @()))
    $subtitleReviewFailure = (-not [bool]$Result.Success -and $reasonCode -match '^SUBTITLE_.*(CONVERT|OCR|EXTRACT|VALIDATION|CONTAINER_UNSUPPORTED|SIDECAR)')
    $lifecycle = if ($status -in @('skipped','blocked','review','stopped')) {
        $status
    } elseif ($subtitleReviewFailure) {
        'review'
    } elseif ([bool]$Result.Success -and $publishState -eq 'pending_publish') {
        'parked'
    } elseif ([bool]$Result.Success) {
        'completed'
    } else {
        'failed'
    }
    if ($lifecycle -eq 'completed' -and [string]::IsNullOrWhiteSpace($pipelineSidecarPath) -and
        -not [string]::IsNullOrWhiteSpace($publishedPath) -and (Get-Command -Name Get-SidecarPath -ErrorAction SilentlyContinue)) {
        try { $pipelineSidecarPath = [string](Get-SidecarPath $publishedPath) } catch {}
    }
    $failureArtifactPath = ''
    if ($lifecycle -in @('failed','blocked','review') -and $Entry.File -and (Get-Command -Name Get-SourceFailureMarkerPath -ErrorAction SilentlyContinue)) {
        # The marker is the correlated failure_record.v1 JSON authority. The
        # similarly named failure artifact path is preserved scratch/media and
        # must never be parsed or linked as terminal JSON proof.
        try { $failureArtifactPath = [string](Get-SourceFailureMarkerPath $Entry.File) } catch {}
    }
    $terminalProof = Resolve-MediaPipelineRunMonitorTerminalArtifact `
        -Lifecycle $lifecycle `
        -RunId $runId `
        -JobId $jobId `
        -PipelineSidecarPath $pipelineSidecarPath `
        -ManifestPath $manifestPath `
        -FailureArtifactPath $failureArtifactPath
    if ([bool]$terminalProof.Verified) {
        if (-not [string]::IsNullOrWhiteSpace([string]$terminalProof.PublishedPath)) { $publishedPath = [string]$terminalProof.PublishedPath }
        if (-not [string]::IsNullOrWhiteSpace([string]$terminalProof.ParkedPath)) { $parkedPath = [string]$terminalProof.ParkedPath }
        if (-not [string]::IsNullOrWhiteSpace([string]$terminalProof.IntendedFinalPath)) { $intendedFinalPath = [string]$terminalProof.IntendedFinalPath }
    }
    $terminalEvidenceMissing = -not [bool]$terminalProof.Verified -and $lifecycle -notin @('skipped','stopped')
    if ($terminalEvidenceMissing) {
        # The process result is correlated runtime evidence, but Completed,
        # Pending Publish, and failure/review outcomes require their exact
        # durable artifact. Keep the accepted item nonterminal so run
        # finalization can fail it honestly; never freeze a false success (or a
        # false artifact-backed failure) that immutability would then preserve.
        $lifecycle = 'unknown'
        if (-not [string]::IsNullOrWhiteSpace([string]$terminalProof.Reason)) {
            $reason = [string]$terminalProof.Reason
        }
        if (-not [string]::IsNullOrWhiteSpace([string]$terminalProof.ReasonCode)) {
            $reasonCode = [string]$terminalProof.ReasonCode
        }
        $retryable = $null
    }
    $sidecarEvidencePaths = if ([bool]$terminalProof.Verified) { @($terminalProof.SidecarPaths) } else { @($sidecarPaths) }
    $sidecarEvidence = @(
        foreach ($sidecarPath in $sidecarEvidencePaths) {
            if ([string]::IsNullOrWhiteSpace([string]$sidecarPath)) { continue }
            [ordered]@{
                kind = if ([System.IO.Path]::GetExtension([string]$sidecarPath).ToLowerInvariant() -eq '.srt') { 'subtitle_srt' } else { 'pipeline_sidecar' }
                state = if ($lifecycle -eq 'parked') { 'parked' } else { 'written' }
                path = [string]$sidecarPath
                reason = ''
                evidence = New-MediaPipelineRunMonitorEvidence `
                    -Source $(if ([bool]$terminalProof.Verified) { [string]$terminalProof.EvidenceSource } else { 'process_file_result' }) `
                    -Provenance $(if ([bool]$terminalProof.Verified) { 'terminal' } else { 'backend_confirmed' })
            }
        }
    )
    $nextAction = if ($terminalEvidenceMissing) {
        'Open Reports and retry only after the missing per-file terminal evidence is understood.'
    } else { switch ($lifecycle) {
        'completed' { 'Open Completed Output for terminal proof.' }
        'parked' { 'Open Pending Publish to review or drain the manifest-backed output.' }
        'review' { 'Open Reports and resolve the review evidence before retrying.' }
        'blocked' { 'Resolve the backend-reported blocker, then start a new run.' }
        'skipped' { 'Review the skip reason; no action is required unless the file should be re-queued.' }
        'stopped' { 'Review stop evidence before starting a new run.' }
        default {
            if ([bool]$terminalProof.Verified -and -not [string]::IsNullOrWhiteSpace([string]$terminalProof.NextAction)) {
                [string]$terminalProof.NextAction
            } elseif ($retryable) {
                'Open Reports, correct the failure, and retry in a new run.'
            } else {
                'Open Reports for operator-owned recovery guidance.'
            }
        }
    } }

    if (-not [string]::IsNullOrWhiteSpace([string]$Result.Route) -and
        (Get-Command -Name Set-MediaPipelineRunMonitorExecutedRoute -ErrorAction SilentlyContinue)) {
        # Process-File reports an encode/remux family at completion. Preserve
        # any exact runtime selection (hardware, CPU fallback, remux tool) that
        # was already authored by the engine; only fill a genuinely absent
        # executed route for older call paths.
        Set-MediaPipelineRunMonitorExecutedRoute -RunId $runId -JobId $jobId -Route ([string]$Result.Route) -Reason ([string]$Result.RouteReason) -ReasonCode ([string]$Result.RouteReasonCode) -OnlyIfAwaiting | Out-Null
    }
    if ([bool]$terminalProof.Verified -and -not [string]::IsNullOrWhiteSpace([string]$terminalProof.Route) -and
        (Get-Command -Name Set-MediaPipelineRunMonitorFinalRoute -ErrorAction SilentlyContinue)) {
        Set-MediaPipelineRunMonitorFinalRoute `
            -RunId $runId `
            -JobId $jobId `
            -Route ([string]$terminalProof.Route) `
            -Reason ([string]$terminalProof.Reason) `
            -ReasonCode ([string]$terminalProof.ReasonCode) `
            -EvidenceSource ([string]$terminalProof.EvidenceSource) | Out-Null
    } elseif ([bool]$terminalProof.Verified -and
        (Get-Command -Name Set-MediaPipelineRunMonitorFinalRouteState -ErrorAction SilentlyContinue)) {
        Set-MediaPipelineRunMonitorFinalRouteState `
            -RunId $runId `
            -JobId $jobId `
            -State unknown `
            -Reason ([string]$terminalProof.Reason) `
            -ReasonCode ([string]$terminalProof.ReasonCode) `
            -EvidenceSource ([string]$terminalProof.EvidenceSource) | Out-Null
    }
    if ([bool]$Result.Success -and [bool]$terminalProof.Verified -and (Get-Command -Name Set-MediaPipelineRunMonitorOutput -ErrorAction SilentlyContinue)) {
        if ($lifecycle -eq 'parked') {
            Set-MediaPipelineRunMonitorOutput -RunId $runId -JobId $jobId -State 'parked' -ParkedPath $parkedPath -IntendedFinalPath $intendedFinalPath -SizeBytes $Result.OutputSizeBytes -VerificationState 'completed' -Sidecars $sidecarEvidence | Out-Null
        } else {
            if ([string]::IsNullOrWhiteSpace($publishedPath)) { $publishedPath = [string]$Result.OutputPath }
            if ([string]::IsNullOrWhiteSpace($intendedFinalPath)) { $intendedFinalPath = $publishedPath }
            Set-MediaPipelineRunMonitorOutput -RunId $runId -JobId $jobId -State 'published' -PublishedPath $publishedPath -IntendedFinalPath $intendedFinalPath -SizeBytes $Result.OutputSizeBytes -VerificationState 'completed' -Sidecars $sidecarEvidence | Out-Null
        }
    } elseif ([bool]$Result.Success -and (Get-Command -Name Set-MediaPipelineRunMonitorOutput -ErrorAction SilentlyContinue)) {
        Set-MediaPipelineRunMonitorOutput `
            -RunId $runId `
            -JobId $jobId `
            -State 'unknown' `
            -WorkingOutputPath ([string]$Result.OutputPath) `
            -IntendedFinalPath $intendedFinalPath `
            -SizeBytes $Result.OutputSizeBytes `
            -VerificationState 'unknown' `
            -Sidecars $sidecarEvidence | Out-Null
    } elseif (-not [bool]$Result.Success -and (Get-Command -Name Set-MediaPipelineRunMonitorOutput -ErrorAction SilentlyContinue)) {
        Set-MediaPipelineRunMonitorOutput -RunId $runId -JobId $jobId -State $(if ($lifecycle -eq 'review') { 'review' } else { 'failed' }) -WorkingOutputPath ([string]$Result.OutputPath) -SizeBytes $Result.OutputSizeBytes -VerificationState $(if ($lifecycle -eq 'review') { 'review' } else { 'failed' }) | Out-Null
    }
    if ([bool]$terminalProof.Verified -and $lifecycle -eq 'parked' -and -not [string]::IsNullOrWhiteSpace($manifestPath)) {
        Add-MediaPipelineRunMonitorTerminalReference -RunId $runId -JobId $jobId -Kind 'pending_publish' -Reference $manifestPath -Path $manifestPath | Out-Null
        Add-MediaPipelineRunMonitorTerminalReference -RunId $runId -JobId $jobId -Kind 'manifest' -Reference $manifestPath -Path $manifestPath | Out-Null
    } elseif ([bool]$terminalProof.Verified -and $lifecycle -eq 'completed' -and -not [string]::IsNullOrWhiteSpace($publishedPath)) {
        Add-MediaPipelineRunMonitorTerminalReference -RunId $runId -JobId $jobId -Kind 'completed' -Reference $publishedPath -Path $publishedPath | Out-Null
        Add-MediaPipelineRunMonitorTerminalReference -RunId $runId -JobId $jobId -Kind 'sidecar' -Reference $pipelineSidecarPath -Path $pipelineSidecarPath | Out-Null
    } elseif ([bool]$terminalProof.Verified -and $lifecycle -in @('failed','blocked','review')) {
        Add-MediaPipelineRunMonitorTerminalReference -RunId $runId -JobId $jobId -Kind $(if ($lifecycle -eq 'review') { 'review' } else { 'failure' }) -Reference $failureArtifactPath -Path $failureArtifactPath | Out-Null
    }
    foreach ($sidecarPath in $(if ([bool]$terminalProof.Verified) { @($terminalProof.SidecarPaths) } else { @() })) {
        if (-not [string]::IsNullOrWhiteSpace([string]$sidecarPath)) {
            Add-MediaPipelineRunMonitorTerminalReference -RunId $runId -JobId $jobId -Kind 'sidecar' -Reference ([string]$sidecarPath) -Path ([string]$sidecarPath) | Out-Null
        }
    }
    $finalEvidenceState = if ([bool]$terminalProof.Verified) {
        switch ($lifecycle) { 'failed' { 'failed' } 'blocked' { 'blocked' } 'review' { 'review' } default { 'completed' } }
    } elseif ($lifecycle -in @('skipped','stopped')) {
        'skipped'
    } else {
        'unknown'
    }
    $finalEvidenceDetail = if ([bool]$terminalProof.Verified) {
        if (-not [string]::IsNullOrWhiteSpace([string]$terminalProof.Reason)) { [string]$terminalProof.Reason } else { $reason }
    } elseif (-not [string]::IsNullOrWhiteSpace([string]$terminalProof.Reason)) {
        [string]$terminalProof.Reason
    } else {
        $reason
    }
    $finalEvidenceReasonCode = if ([bool]$terminalProof.Verified -and -not [string]::IsNullOrWhiteSpace([string]$terminalProof.ReasonCode)) {
        [string]$terminalProof.ReasonCode
    } elseif (-not [bool]$terminalProof.Verified -and -not [string]::IsNullOrWhiteSpace([string]$terminalProof.ReasonCode)) {
        [string]$terminalProof.ReasonCode
    } else {
        $reasonCode
    }
    Set-MediaPipelineRunMonitorStage `
        -RunId $runId `
        -JobId $jobId `
        -StageId 'final_evidence' `
        -State $finalEvidenceState `
        -Detail $finalEvidenceDetail `
        -ReasonCode $finalEvidenceReasonCode `
        -EvidenceSource $(if ([bool]$terminalProof.Verified) { [string]$terminalProof.EvidenceSource } else { 'process_file_result' }) | Out-Null
    Sync-MediaPipelineRunMonitorTerminalTracks -RunId $runId -JobId $jobId -TerminalProof $terminalProof
    Set-MediaPipelineRunMonitorItemLifecycle -RunId $runId -JobId $jobId -State $lifecycle -Reason $reason -ReasonCode $reasonCode -Retryable $retryable -RecoveryOwner $(if ($lifecycle -in @('failed','blocked','review')) { 'operator' } else { 'pipeline' }) -NextAction $nextAction | Out-Null
}

function Write-MediaPipelineUnexpectedQueueEntryFailure {
    param(
        [Parameter(Mandatory)] $Entry,
        [Parameter(Mandatory)] $ErrorRecord
    )

    $file = $Entry.File
    $sourcePath = if ($file -and $file.PSObject.Properties['FullName']) { [string]$file.FullName } else { [string]$Entry.SourcePath }
    $sourceName = if ($file -and $file.PSObject.Properties['Name']) { [string]$file.Name } else { Split-Path $sourcePath -Leaf }
    $message = if ($ErrorRecord.Exception -and $ErrorRecord.Exception.Message) { [string]$ErrorRecord.Exception.Message } else { [string]$ErrorRecord }
    Write-Log "Unexpected queue item failure for ${sourceName}: $message" 'ERROR'
    $script:UnexpectedQueueEntryFailures = [int]$script:UnexpectedQueueEntryFailures + 1
    $script:totalFailed = [int]$script:totalFailed + 1

    if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
        try {
            Write-PipelineEvent -EventType 'queue_item_unexpected_failure' -Stage 'processing' -Status 'failed' -SourcePath $sourcePath -Data @{
                source_name = $sourceName
                error_code  = 'UNEXPECTED_PIPELINE_EXCEPTION'
                error       = $message
                category    = ([string]$Entry.LocalWorkerPhase)
                retryable   = $true
            } | Out-Null
        } catch {}
    }

    if ($file -and (Get-Command -Name Register-SourceFailure -ErrorAction SilentlyContinue)) {
        try {
            Register-SourceFailure `
                -SourceFile $file `
                -Classification 'transient' `
                -Reason "Unexpected queue item failure: $message" `
                -Stage 'queue-item' `
                -ErrorCode 'UNEXPECTED_PIPELINE_EXCEPTION' `
                -SuggestedAction 'Inspect the failure report and retry after confirming the source and runtime state are healthy.' | Out-Null
        } catch {
            Write-Log "Failed to record unexpected queue item failure for ${sourceName}: $_" 'WARN'
        }
    }

    return [pscustomobject]@{
        Status            = 'failed'
        Success           = $false
        QueueTerminal     = $false
        Retryable         = $true
        UnexpectedFailure = $true
        ErrorCode         = 'UNEXPECTED_PIPELINE_EXCEPTION'
        Reason            = $message
        SourcePath        = $sourcePath
    }
}

function Invoke-MediaPipelineProcessQueueEntrySafely {
    param(
        [Parameter(Mandatory)] $Entry,
        [Parameter(Mandatory)] $ProcessedIndex,
        [switch] $StopOnUnexpectedFailure
    )

    $previousRunMonitorJobId = [string]$script:CurrentRunMonitorJobId
    $script:CurrentRunMonitorJobId = [string]$Entry.RunMonitorJobId
    $result = $null
    $unexpectedError = $null
    try {
        Start-MediaPipelineRunMonitorQueueEntry -Entry $Entry
        $result = Invoke-MediaPipelineProcessQueueEntry -Entry $Entry -ProcessedIndex $ProcessedIndex
    } catch {
        $unexpectedError = $_
        $result = Write-MediaPipelineUnexpectedQueueEntryFailure -Entry $Entry -ErrorRecord $_
    } finally {
        if ($null -ne $result) {
            Complete-MediaPipelineRunMonitorQueueEntry -Entry $Entry -Result $result
        }
        $script:CurrentRunMonitorJobId = $previousRunMonitorJobId
    }
    if ($null -ne $unexpectedError -and $StopOnUnexpectedFailure) {
        throw $unexpectedError
    }
    return $result
}

function Get-MediaPipelineQueueDispatchBoundaryState {
    Check-ControlFlags
    if ([bool]$script:StopRequested) { return 'immediate_stop' }
    if (Test-MediaPipelineStopAfterCurrentBoundary) { return 'stop_after_current' }
    return ''
}

function Invoke-MediaQueuePhasePlan {
    param(
        [Parameter(Mandatory)] $QueuePlan,
        [Parameter(Mandatory)] $ProcessedIndex,
        [switch] $StopOnUnexpectedFailure
    )

    $runnableEntries = @(Get-MediaPipelineQueuePlanRunnableEntries -QueuePlan $QueuePlan)
    $stoppedAfterCurrent = $false
    # ---- Phase 1: High-priority movies ----
    $highMovies = @($runnableEntries | Where-Object { [string]$_.LocalWorkerPhase -eq 'priority_movie' })
    # ---- Phase 2: High-priority TV ----
    $highTV = @($runnableEntries | Where-Object { [string]$_.LocalWorkerPhase -eq 'priority_tv' })
    $mixedPriorityEntries = @($runnableEntries | Where-Object { [string]$_.LocalWorkerPhase -eq 'priority' })
    # ---- Combined priority count for logging ----
    $totalHighCount = $highMovies.Count + $highTV.Count + $mixedPriorityEntries.Count

    if ($QueuePlan.MixPriorityPhase -and $totalHighCount -gt 0) {
        # MixPriorityPhase: run all high-priority items (movies + TV) together
        $mixedPriority = @($mixedPriorityEntries)
        $mixedMovieCount = @($mixedPriority | Where-Object { -not [bool]$_.IsTV }).Count
        $mixedTVCount = @($mixedPriority | Where-Object { [bool]$_.IsTV }).Count
        Write-Log "PRIORITY PHASE (mixed): $($mixedPriority.Count) item(s) queued first (movies: $mixedMovieCount, tv: $mixedTVCount)"
        foreach ($entry in $mixedPriority) {
            $boundaryState = Get-MediaPipelineQueueDispatchBoundaryState
            if ($boundaryState) { if ($boundaryState -eq 'stop_after_current') { $stoppedAfterCurrent = $true }; break }
            Invoke-MediaPipelineProcessQueueEntrySafely -Entry $entry -ProcessedIndex $ProcessedIndex -StopOnUnexpectedFailure:$StopOnUnexpectedFailure
        }
    } else {
        # Default: priority movies first, then priority TV
        if ($highMovies.Count -gt 0) {
            Write-Log "PRIORITY PHASE — MOVIES: $($highMovies.Count) item(s)"
            for ($i = 0; $i -lt $highMovies.Count; $i++) {
                $boundaryState = Get-MediaPipelineQueueDispatchBoundaryState
                if ($boundaryState) { if ($boundaryState -eq 'stop_after_current') { $stoppedAfterCurrent = $true }; break }
                $entry = $highMovies[$i]
                Invoke-MediaPipelineProcessQueueEntrySafely -Entry $entry -ProcessedIndex $ProcessedIndex -StopOnUnexpectedFailure:$StopOnUnexpectedFailure
            }
        }
        if (-not $script:StopRequested -and -not $stoppedAfterCurrent -and $highTV.Count -gt 0) {
            Write-Log "PRIORITY PHASE — TV: $($highTV.Count) item(s)"
            for ($i = 0; $i -lt $highTV.Count; $i++) {
                $boundaryState = Get-MediaPipelineQueueDispatchBoundaryState
                if ($boundaryState) { if ($boundaryState -eq 'stop_after_current') { $stoppedAfterCurrent = $true }; break }
                $entry = $highTV[$i]
                Invoke-MediaPipelineProcessQueueEntrySafely -Entry $entry -ProcessedIndex $ProcessedIndex -StopOnUnexpectedFailure:$StopOnUnexpectedFailure
            }
        }
    }

    # ---- Phase 3: Normal movies ----
    if (-not $script:StopRequested -and -not $stoppedAfterCurrent) {
        $normalMovieEntries = @($runnableEntries | Where-Object { [string]$_.LocalWorkerPhase -eq 'movie' })
        for ($i = 0; $i -lt $normalMovieEntries.Count; $i++) {
            $boundaryState = Get-MediaPipelineQueueDispatchBoundaryState
            if ($boundaryState) { if ($boundaryState -eq 'stop_after_current') { $stoppedAfterCurrent = $true }; break }
            $entry = $normalMovieEntries[$i]
            Invoke-MediaPipelineProcessQueueEntrySafely -Entry $entry -ProcessedIndex $ProcessedIndex -StopOnUnexpectedFailure:$StopOnUnexpectedFailure
        }
    }

    # ---- Phase 4: Normal TV ----
    if (-not $script:StopRequested -and -not $stoppedAfterCurrent) {
        $normalTvEntries = @($runnableEntries | Where-Object { [string]$_.LocalWorkerPhase -eq 'tv' })
        for ($i = 0; $i -lt $normalTvEntries.Count; $i++) {
            $boundaryState = Get-MediaPipelineQueueDispatchBoundaryState
            if ($boundaryState) { if ($boundaryState -eq 'stop_after_current') { $stoppedAfterCurrent = $true }; break }
            $entry = $normalTvEntries[$i]
            Invoke-MediaPipelineProcessQueueEntrySafely -Entry $entry -ProcessedIndex $ProcessedIndex -StopOnUnexpectedFailure:$StopOnUnexpectedFailure
        }
    }

    # ---- Phase 5: Low-priority entries (movies and TV interleaved, already sorted) ----
    if (-not $script:StopRequested -and -not $stoppedAfterCurrent) {
        $lowEntries = @($runnableEntries | Where-Object { [string]$_.LocalWorkerPhase -eq 'low' })
        if ($lowEntries.Count -gt 0) {
            Write-Log "LOW-PRIORITY PHASE: $($lowEntries.Count) item(s) deferred"
            for ($i = 0; $i -lt $lowEntries.Count; $i++) {
                $boundaryState = Get-MediaPipelineQueueDispatchBoundaryState
                if ($boundaryState) { if ($boundaryState -eq 'stop_after_current') { $stoppedAfterCurrent = $true }; break }
                $entry = $lowEntries[$i]
                Invoke-MediaPipelineProcessQueueEntrySafely -Entry $entry -ProcessedIndex $ProcessedIndex -StopOnUnexpectedFailure:$StopOnUnexpectedFailure
            }
        }
    }

    # ---- Hold entries are never processed ----
    $holdCount = [int]$QueuePlan.HoldCount
    if ($holdCount -gt 0) {
        Write-Log "HOLD: $holdCount item(s) excluded from processing this round (operator hold)"
    }

    return [pscustomobject]@{
        Stopped       = [bool]$script:StopRequested
        StoppedAfterCurrent = [bool]$stoppedAfterCurrent
        PriorityCount = $totalHighCount
        MovieCount    = [int]$QueuePlan.MovieCount
        TVCount       = [int]$QueuePlan.TVCount
        LowCount      = $QueuePlan.LowCount
        HoldCount     = $holdCount
        UnexpectedFailures = [int]$script:UnexpectedQueueEntryFailures
    }
}
