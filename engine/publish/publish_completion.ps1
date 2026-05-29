# Publish-completion orchestration for completed local outputs.
# Dot-sourced by MediaPipeline_chatgpt.ps1; dependencies are resolved at call time.

function Test-PublishCopyFailureIsOutputSpace {
    $copyResult = $script:LastCopyFileRobocopyResult
    if ($null -eq $copyResult) { return $false }
    $reasonCode = ''
    if ($copyResult.PSObject.Properties['ReasonCode']) {
        $reasonCode = [string]$copyResult.ReasonCode
    }
    if ($reasonCode -in @('OUTPUT_DESTINATION_LOW_SPACE', 'OUTPUT_DESTINATION_SPACE_UNKNOWN')) { return $true }
    $reason = if ($copyResult.PSObject.Properties['Reason']) { [string]$copyResult.Reason } else { '' }
    return ($reason -match 'insufficient free space|not enough space|disk full|No space left on device')
}

function Test-PublishCopyFailureIsOutputSpaceUnknown {
    $copyResult = $script:LastCopyFileRobocopyResult
    if ($null -eq $copyResult) { return $false }
    if (-not $copyResult.PSObject.Properties['ReasonCode']) { return $false }
    return ([string]$copyResult.ReasonCode -eq 'OUTPUT_DESTINATION_SPACE_UNKNOWN')
}

function Get-PublishCopyFailureReason {
    $copyResult = $script:LastCopyFileRobocopyResult
    if ($null -eq $copyResult) { return '' }
    if ($copyResult.PSObject.Properties['Reason']) { return [string]$copyResult.Reason }
    return ''
}

function Complete-PipelineOutputPublish {
    param(
        [Parameter(Mandatory)] $SourceFile,
        [Parameter(Mandatory)] [string] $ScratchPath,
        [Parameter(Mandatory)] $Paths,
        [Parameter(Mandatory)] [string] $Route,
        [Parameter(Mandatory)] [string] $ProgressRoute,
        [Parameter(Mandatory)] [string] $StagePrefix,
        [Parameter(Mandatory)] [string] $Context,
        [string] $RouteReasonCode = '',
        [string] $RouteReason = '',
        [array] $Tx3gTracks = @(),
        [array] $BdpgsTracks = @()
    )

    $sourceIdentity = Get-SourceIdentityKey $SourceFile
    $sourceIdentityV2 = Get-SourceIdentityKeyV2 $SourceFile
    $sourceMTimeUtc = $SourceFile.LastWriteTimeUtc.ToString('o')
    $publishTxn = New-PublishTransactionId
    $stageName = $StagePrefix.ToLowerInvariant()
    $logPrefix = $StagePrefix.ToUpperInvariant()
    if ([string]::IsNullOrWhiteSpace($RouteReasonCode) -and $script:CurrentRouteReasonCode) {
        $RouteReasonCode = [string]$script:CurrentRouteReasonCode
    }
    if ([string]::IsNullOrWhiteSpace($RouteReason) -and $script:CurrentRouteReason) {
        $RouteReason = [string]$script:CurrentRouteReason
    }
    $folderPolicyMetadata = if (Get-Command -Name Get-ActiveFolderPolicyMetadata -ErrorAction SilentlyContinue) {
        Get-ActiveFolderPolicyMetadata
    } else {
        $null
    }
    $routePlanMetadata = if (Get-Command -Name Get-ActiveMediaRoutePlanMetadata -ErrorAction SilentlyContinue) {
        Get-ActiveMediaRoutePlanMetadata
    } else {
        $null
    }
    # S9 — compute media_type once at the top of the function so every
    # parkArgs hashtable below (deferred publish, AV-push failure park,
    # sidecar-write failure park, tx3g-publish failure park, etc.) can
    # carry it through to the manifest. Without this, deferred-published
    # movies still came back blank in the Completed tab even after the
    # immediate-publish path was fixed.
    $sidecarMediaType = ''
    $plexPlan = $null
    if ($Paths -is [System.Collections.IDictionary] -and $Paths.Contains('PlexPlan')) {
        $plexPlan = $Paths['PlexPlan']
    } elseif ($Paths -and $Paths.PSObject.Properties['PlexPlan']) {
        $plexPlan = $Paths.PlexPlan
    }
    if ($plexPlan) {
        $planMediaKind = [string]$plexPlan.MediaKind
        if (-not [string]::IsNullOrWhiteSpace($planMediaKind)) {
            $sidecarMediaType = $planMediaKind.Trim().ToLowerInvariant()
        }
    }

    if ($script:DeferredPublish) {
        Set-ProgressStage -Stage 'push' -Status $script:pipelineStatus -Route $ProgressRoute -PushState 'deferred' -Percent 100 -SaveNow
        $parkArgs = @{
            LocalOut = $Paths.LocalOut; ServerOut = $Paths.ServerOut; Route = $Route
            MediaType = $sidecarMediaType
            RouteReasonCode = $RouteReasonCode; RouteReason = $RouteReason
            SourceIdentity = $sourceIdentity; SourceIdentityV2 = $sourceIdentityV2
            SourcePath = $SourceFile.FullName; SourceSize = $SourceFile.Length; SourceMTimeUtc = $sourceMTimeUtc
            PublishTransactionId = $publishTxn; PublishMode = 'deferred'
            FolderPolicyMetadata = $folderPolicyMetadata
            RoutePlanMetadata = $routePlanMetadata
        }
        if (-not (Invoke-ParkPendingPushWithTx3gSidecars -SourceFile $SourceFile -ScratchPath $ScratchPath -Tx3gTracks @($Tx3gTracks) -BdpgsTracks @($BdpgsTracks) -MediaOutputPath $Paths.ServerOut -ParkArgs $parkArgs -Context $Context)) {
            Add-RoundFailureRecord -SourcePath $SourceFile.FullName -Stage "$stageName-deferred-publish" -Reason 'Deferred publish is enabled but the completed local output and subtitle sidecars could not be parked' -Classification 'transient' -ArtifactPath $Paths.LocalOut -SuggestedAction 'Inspect scratch-disk write permissions or PendingServerPush availability.'
            return New-PipelinePublishResult -Ok:$false -DeleteLocalOutput:$false -KeepScratchInput:$false -PublishState 'failed' -PublishMode 'deferred' -OutputPath $Paths.LocalOut -Reason 'Deferred publish park failed'
        }
        Clear-SourceFailureState $SourceFile
        Write-Log "$logPrefix deferred publish: parked $(Split-Path $Paths.ServerOut -Leaf) in PendingServerPush for later upload"
        $localSize = (Get-Item -LiteralPath $Paths.LocalOut -ErrorAction SilentlyContinue).Length
        return New-PipelinePublishResult -Ok:$true -DeleteLocalOutput:$false -KeepScratchInput:$false -PublishState 'pending_publish' -PublishMode 'deferred' -OutputPath $Paths.ServerOut -OutputSizeBytes ([long]$localSize)
    }

    $tx3gPublishPlan = New-Tx3gSrtSidecarPublishPlan -Tx3gTracks @($Tx3gTracks) -MediaOutputPath $Paths.ServerOut -Context $Context
    if ($tx3gPublishPlan.Failures -and @($tx3gPublishPlan.Failures).Count -gt 0) {
        Register-Tx3gSubtitleFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Failures @($tx3gPublishPlan.Failures) -Stage 'subtitle-tx3g-publish'
        Add-RoundFailureRecord -SourcePath $SourceFile.FullName -Stage "$stageName-tx3g-sidecar" -Reason 'TX3G SRT sidecar publish preflight failed before server media was copied' -Classification 'transient' -SuggestedAction 'Inspect generated TX3G SRT sidecars and retry; server media was not revealed.' | Out-Null
        $parkArgs = @{
            LocalOut = $Paths.LocalOut; ServerOut = $Paths.ServerOut; Route = $Route
            MediaType = $sidecarMediaType
            RouteReasonCode = $RouteReasonCode; RouteReason = $RouteReason
            SourceIdentity = $sourceIdentity; SourceIdentityV2 = $sourceIdentityV2
            SourcePath = $SourceFile.FullName; SourceSize = $SourceFile.Length; SourceMTimeUtc = $sourceMTimeUtc
            PublishTransactionId = $publishTxn; PublishMode = 'retry'
            FolderPolicyMetadata = $folderPolicyMetadata
            RoutePlanMetadata = $routePlanMetadata
            Tx3gSrtTracks = @($tx3gPublishPlan.Tracks)
            Tx3gSrtFailures = @($tx3gPublishPlan.Failures)
            BdpgsSrtFailures = @()
            Tx3gEmbeddedSrtTracks = @(ConvertTo-Tx3gEmbeddedSrtTrackRecords -Tx3gTracks @($Tx3gTracks))
            BdpgsEmbeddedSrtTracks = @(ConvertTo-BdpgsEmbeddedSrtTrackRecords -BdpgsTracks @($BdpgsTracks))
            Tx3gSrtConversionEnabled = [bool]$script:ConvertTx3gToSrt
            Tx3gExternalSrtSidecarsEnabled = [bool]$script:CreateExternalTx3gSrtSidecars
            DropTx3gAfterConversion = [bool]$script:DropTx3gAfterConversion
            BdpgsSrtConversionEnabled = [bool]$script:ConvertBdpgsToSrt
            DropBdpgsAfterConversion = [bool]$script:DropBdpgsAfterConversion
        }
        if (-not (Invoke-ParkPendingPush @parkArgs)) {
            Write-Log "${logPrefix}: could not park the verified local output after tx3g sidecar preflight failure; leaving it in place at $($Paths.LocalOut)" "ERROR"
        }
        return New-PipelinePublishResult -Ok:$false -DeleteLocalOutput:$false -KeepScratchInput:$true -PublishState 'failed' -PublishMode 'retry' -OutputPath $Paths.LocalOut -Reason 'TX3G sidecar publish preflight failed'
    }

    $serverPartialOut = New-PublishPartialMediaPath -ServerOut $Paths.ServerOut -PublishTransactionId $publishTxn
    Remove-PublishPartialMedia -Path $serverPartialOut

    Set-ProgressStage -Stage 'push' -Status $script:pipelineStatus -Route $ProgressRoute -PushState 'copying' -Percent $null -SaveNow
    if (-not (Copy-FileRobocopy $Paths.LocalOut $serverPartialOut)) {
        $copyFailureIsOutputSpace = Test-PublishCopyFailureIsOutputSpace
        $copyFailureIsOutputSpaceUnknown = Test-PublishCopyFailureIsOutputSpaceUnknown
        $copyFailureReason = Get-PublishCopyFailureReason
        if ($copyFailureIsOutputSpace) {
            Set-ProgressStage -Stage 'push' -Status $script:pipelineStatus -Route $ProgressRoute -PushState 'deferred' -Percent 100 -SaveNow
            $outputSpaceMessage = if ($copyFailureIsOutputSpaceUnknown) {
                'output destination free space could not be verified'
            } else {
                'output destination has insufficient free space'
            }
            Write-Log "${logPrefix}: $outputSpaceMessage — parking output in PendingServerPush for later upload" "WARN"
        } else {
            Set-ProgressStage -Stage 'push' -Status $script:pipelineStatus -Route $ProgressRoute -PushState 'failed' -Percent $null -SaveNow
            Write-Log "${logPrefix}: server push failed — parking output in PendingServerPush" "ERROR"
            Add-RoundFailureRecord -SourcePath $SourceFile.FullName -Stage "$stageName-push" -Reason 'Server push failed; local output parked for retry' -Classification 'transient' -ArtifactPath $Paths.LocalOut -SuggestedAction 'Inspect share connectivity or free space; the verified local output is parked in PendingServerPush for the next retry.'
        }
        $parkArgs = @{
            LocalOut = $Paths.LocalOut; ServerOut = $Paths.ServerOut; Route = $Route
            MediaType = $sidecarMediaType
            RouteReasonCode = $RouteReasonCode; RouteReason = $RouteReason
            SourceIdentity = $sourceIdentity; SourceIdentityV2 = $sourceIdentityV2
            SourcePath = $SourceFile.FullName; SourceSize = $SourceFile.Length; SourceMTimeUtc = $sourceMTimeUtc
            PublishTransactionId = $publishTxn; PublishMode = $(if ($copyFailureIsOutputSpace) { 'output-space-deferred' } else { 'retry' })
            FolderPolicyMetadata = $folderPolicyMetadata
            RoutePlanMetadata = $routePlanMetadata
        }
        if (-not (Invoke-ParkPendingPushWithTx3gSidecars -SourceFile $SourceFile -ScratchPath $ScratchPath -Tx3gTracks @($Tx3gTracks) -BdpgsTracks @($BdpgsTracks) -MediaOutputPath $Paths.ServerOut -ParkArgs $parkArgs -Context $Context)) {
            Write-Log "${logPrefix}: could not park the verified local output and tx3g sidecars after push failure; leaving output in place at $($Paths.LocalOut)" "ERROR"
            if ($copyFailureIsOutputSpace) {
                $reason = if ([string]::IsNullOrWhiteSpace($copyFailureReason)) {
                    if ($copyFailureIsOutputSpaceUnknown) {
                        'Output destination free space could not be verified and the completed local output could not be parked'
                    } else {
                        'Output destination has insufficient free space and the completed local output could not be parked'
                    }
                } else {
                    if ($copyFailureIsOutputSpaceUnknown) {
                        "Output destination free space could not be verified and the completed local output could not be parked: $copyFailureReason"
                    } else {
                        "Output destination has insufficient free space and the completed local output could not be parked: $copyFailureReason"
                    }
                }
                $errorCode = if ($copyFailureIsOutputSpaceUnknown) { 'OUTPUT_DESTINATION_SPACE_UNKNOWN' } else { 'OUTPUT_DESTINATION_LOW_SPACE' }
                $suggestedAction = if ($copyFailureIsOutputSpaceUnknown) {
                    'Restore destination free-space visibility/connectivity and inspect PendingServerPush/scratch permissions; the verified local output could not be safely parked.'
                } else {
                    'Free space on the output destination and inspect PendingServerPush/scratch permissions; the verified local output could not be safely parked.'
                }
                Add-RoundFailureRecord -SourcePath $SourceFile.FullName -Stage "$stageName-push-park" -Reason $reason -Classification 'transient' -ErrorCode $errorCode -ArtifactPath $Paths.LocalOut -SuggestedAction $suggestedAction
            }
            return New-PipelinePublishResult -Ok:$false -DeleteLocalOutput:$false -KeepScratchInput:$false -PublishState 'failed' -PublishMode $(if ($copyFailureIsOutputSpace) { 'output-space-deferred' } else { 'retry' }) -OutputPath $Paths.LocalOut -Reason 'Could not park output after publish copy failure'
        }
        if ($copyFailureIsOutputSpace) {
            Clear-SourceFailureState $SourceFile
            Write-Log "$logPrefix output-space deferred publish: parked $(Split-Path $Paths.ServerOut -Leaf) in PendingServerPush; not counted as a processing failure"
            $localSize = (Get-Item -LiteralPath $Paths.LocalOut -ErrorAction SilentlyContinue).Length
            return New-PipelinePublishResult -Ok:$true -DeleteLocalOutput:$false -KeepScratchInput:$false -PublishState 'pending_publish' -PublishMode 'output-space-deferred' -OutputPath $Paths.ServerOut -OutputSizeBytes ([long]$localSize) -ParkedForOutputSpace:$true
        }
        return New-PipelinePublishResult -Ok:$false -DeleteLocalOutput:$false -KeepScratchInput:$false -PublishState 'failed' -PublishMode 'retry' -OutputPath $Paths.LocalOut -Reason 'Server push failed; output parked for retry'
    }
    Set-ProgressStage -Stage 'push' -Status $script:pipelineStatus -Route $ProgressRoute -PushState 'copied_pending_reveal' -Percent 95 -SaveNow

    $tx3gSidecars = Publish-Tx3gSrtSidecarsFromPlan -Plan $tx3gPublishPlan -Context $Context
    if ($tx3gSidecars.Failures -and @($tx3gSidecars.Failures).Count -gt 0) {
        Register-Tx3gSubtitleFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Failures @($tx3gSidecars.Failures) -Stage 'subtitle-tx3g-publish'
        Add-RoundFailureRecord -SourcePath $SourceFile.FullName -Stage "$stageName-tx3g-sidecar" -Reason 'Server partial copy succeeded but tx3g SRT sidecar publish failed before final media reveal' -Classification 'transient' -SuggestedAction 'Inspect share permissions or antivirus locks on SRT sidecar writes; final server media was not revealed and the local output is being parked for retry.'
        $parkArgs = @{
            LocalOut = $Paths.LocalOut; ServerOut = $Paths.ServerOut; Route = $Route
            MediaType = $sidecarMediaType
            RouteReasonCode = $RouteReasonCode; RouteReason = $RouteReason
            SourceIdentity = $sourceIdentity; SourceIdentityV2 = $sourceIdentityV2
            SourcePath = $SourceFile.FullName; SourceSize = $SourceFile.Length; SourceMTimeUtc = $sourceMTimeUtc
            PublishTransactionId = $publishTxn; PublishMode = 'retry'
            FolderPolicyMetadata = $folderPolicyMetadata
            RoutePlanMetadata = $routePlanMetadata
        }
        if (-not (Invoke-ParkPendingPushWithTx3gSidecars -SourceFile $SourceFile -ScratchPath $ScratchPath -Tx3gTracks @($Tx3gTracks) -BdpgsTracks @($BdpgsTracks) -MediaOutputPath $Paths.ServerOut -ParkArgs $parkArgs -Context $Context)) {
            Write-Log "${logPrefix}: could not park the verified local output after tx3g sidecar failure; leaving it in place at $($Paths.LocalOut)" "ERROR"
        }
        Remove-PublishPartialMedia -Path $serverPartialOut
        return New-PipelinePublishResult -Ok:$false -DeleteLocalOutput:$false -KeepScratchInput:$true -PublishState 'failed' -PublishMode 'retry' -OutputPath $Paths.LocalOut -Reason 'TX3G sidecar publish failed before final media reveal'
    }

    $selectedEncodeAttempt = $null
    if ($script:CurrentEncodeAttempts) {
        $successfulAttempts = @($script:CurrentEncodeAttempts | Where-Object { $_.success })
        if ($successfulAttempts.Count -gt 0) {
            $selectedEncodeAttempt = $successfulAttempts | Select-Object -Last 1
        } else {
            $selectedEncodeAttempt = @($script:CurrentEncodeAttempts) | Select-Object -Last 1
        }
    }

    # Movie outputs land directly under $Outsource (no "Movies" library
    # folder) by default, while TV outputs land under "TV\<Show>\Season XX".
    # The desktop's path-based media_type derivation only matched literal
    # 'tv' or 'movies' segments, so movies came back blank in the
    # Completed tab. Surface MediaKind from the destination plan
    # explicitly so future records are unambiguous; the desktop falls
    # back to path heuristics for sidecars written before this fix.
    # ($sidecarMediaType is computed at the top of this function so
    # every parkArgs branch can carry it through to the manifest.)
    $sidecarExtra = [ordered]@{
        output_path            = $Paths.ServerOut
        media_type             = $sidecarMediaType
        route_reason_code      = $RouteReasonCode
        route_reason           = $RouteReason
        publish_state          = 'published'
        publish_mode           = 'immediate'
        publish_transaction_id = $publishTxn
        encode_selected_attempt = $selectedEncodeAttempt
        encode_selected_encoder = if ($selectedEncodeAttempt) { [string]$selectedEncodeAttempt.selected_encoder } else { '' }
        encode_selected_encoder_kind = if ($selectedEncodeAttempt) { [string]$selectedEncodeAttempt.encoder_kind } else { '' }
        encode_selected_gpu_device = if ($selectedEncodeAttempt) { [string]$selectedEncodeAttempt.selected_gpu_device } else { '' }
        audio_decisions        = if (Get-Command -Name Get-LastAudioDecisionRecords -ErrorAction SilentlyContinue) { @(Get-LastAudioDecisionRecords) } else { @() }
        subtitle_decisions     = if (Get-Command -Name Get-LastSubtitleDecisionRecords -ErrorAction SilentlyContinue) { @(Get-LastSubtitleDecisionRecords) } else { @() }
        source_identity        = $sourceIdentity
        source_identity_v2     = $sourceIdentityV2
        source_identity_v2_algorithm = $script:SourceIdentityV2Algorithm
        source_path            = $SourceFile.FullName
        source_size            = $SourceFile.Length
        source_mtime_utc       = $sourceMTimeUtc
        output_size            = (Get-Item -LiteralPath $serverPartialOut -ErrorAction SilentlyContinue).Length
        tx3g_srt_tracks        = @($tx3gSidecars.Tracks)
        tx3g_srt_failures      = @($tx3gSidecars.Failures)
        bdpgs_srt_failures     = @()
        tx3g_embedded_srt_tracks = @(ConvertTo-Tx3gEmbeddedSrtTrackRecords -Tx3gTracks @($Tx3gTracks))
        bdpgs_embedded_srt_tracks = @(ConvertTo-BdpgsEmbeddedSrtTrackRecords -BdpgsTracks @($BdpgsTracks))
        tx3g_srt_conversion_enabled = [bool]$script:ConvertTx3gToSrt
        tx3g_external_srt_sidecars_enabled = [bool]$script:CreateExternalTx3gSrtSidecars
        drop_tx3g_after_conversion = [bool]$script:DropTx3gAfterConversion
        bdpgs_srt_conversion_enabled = [bool]$script:ConvertBdpgsToSrt
        drop_bdpgs_after_conversion = [bool]$script:DropBdpgsAfterConversion
        elapsed_seconds        = if ($script:currentItemStartedAt) { [math]::Round(((Get-Date) - $script:currentItemStartedAt).TotalSeconds, 1) } else { $null }
    }
    if ($folderPolicyMetadata) { $sidecarExtra['folder_policy'] = $folderPolicyMetadata }
    if (Get-Command -Name Add-MediaRoutePlanMetadataToMap -ErrorAction SilentlyContinue) {
        Add-MediaRoutePlanMetadataToMap -Map $sidecarExtra -Metadata $routePlanMetadata | Out-Null
    } elseif ($routePlanMetadata) {
        $sidecarExtra['route_plan'] = $routePlanMetadata
    }

    $publishSidecarBackup = Backup-PublishSidecarForReveal -OutputPath $Paths.ServerOut -PublishTransactionId $publishTxn -Context $Context
    Set-ProgressStage -Stage 'sidecar' -Status $script:pipelineStatus -Route $ProgressRoute -SidecarState 'writing' -Percent $null -SaveNow
    if (Get-Command -Name Write-SubtitleSidecarProgress -ErrorAction SilentlyContinue) {
        Write-SubtitleSidecarProgress -Status 'Writing pipeline sidecar subtitle evidence' -Detail (Split-Path -Leaf (Get-SidecarPath $Paths.ServerOut))
    }
    if (-not (Write-Sidecar -OutputPath $Paths.ServerOut -Route $Route -Extra $sidecarExtra -SkipCompletedManifest)) {
        Write-Log "${logPrefix}: sidecar write failed before final media reveal — removing server partial and parking local copy for retry" "ERROR"
        Set-ProgressStage -Stage 'sidecar' -Status $script:pipelineStatus -Route $ProgressRoute -SidecarState 'failed' -Percent $null -SaveNow
        if (Get-Command -Name Write-SubtitleSidecarProgress -ErrorAction SilentlyContinue) {
            Write-SubtitleSidecarProgress -Status 'Pipeline sidecar subtitle evidence failed' -Detail 'Sidecar write failed before final media reveal' -Failed
        }
        Add-RoundFailureRecord -SourcePath $SourceFile.FullName -Stage "$stageName-sidecar" -Reason 'Server partial copy succeeded but sidecar write failed before final media reveal' -Classification 'transient' -SuggestedAction 'Inspect share permissions or antivirus locks on sidecar writes; final server media was not revealed and the local output is being parked for retry.'
        $parkArgs = @{
            LocalOut = $Paths.LocalOut; ServerOut = $Paths.ServerOut; Route = $Route
            MediaType = $sidecarMediaType
            RouteReasonCode = $RouteReasonCode; RouteReason = $RouteReason
            SourceIdentity = $sourceIdentity; SourceIdentityV2 = $sourceIdentityV2
            SourcePath = $SourceFile.FullName; SourceSize = $SourceFile.Length; SourceMTimeUtc = $sourceMTimeUtc
            PublishTransactionId = $publishTxn; PublishMode = 'retry'
            FolderPolicyMetadata = $folderPolicyMetadata
            RoutePlanMetadata = $routePlanMetadata
        }
        if (-not (Invoke-ParkPendingPushWithTx3gSidecars -SourceFile $SourceFile -ScratchPath $ScratchPath -Tx3gTracks @($Tx3gTracks) -BdpgsTracks @($BdpgsTracks) -MediaOutputPath $Paths.ServerOut -ParkArgs $parkArgs -Context $Context)) {
            Write-Log "${logPrefix}: could not park the verified local output after sidecar failure; leaving it in place at $($Paths.LocalOut)" "ERROR"
        }
        Restore-PublishSidecarAfterRevealFailure -OutputPath $Paths.ServerOut -BackupPath $publishSidecarBackup -Context $Context
        Remove-PublishPartialMedia -Path $serverPartialOut
        return New-PipelinePublishResult -Ok:$false -DeleteLocalOutput:$false -KeepScratchInput:$false -PublishState 'failed' -PublishMode 'retry' -OutputPath $Paths.LocalOut -Reason 'Sidecar write failed before final media reveal'
    }

    Set-ProgressStage -Stage 'sidecar' -Status $script:pipelineStatus -Route $ProgressRoute -SidecarState 'complete' -Percent 100 -SaveNow
    if (Get-Command -Name Write-SubtitleSidecarProgress -ErrorAction SilentlyContinue) {
        Write-SubtitleSidecarProgress -Status 'Pipeline sidecar subtitle evidence written' -Detail (Split-Path -Leaf (Get-SidecarPath $Paths.ServerOut)) -Completed
    }
    Set-ProgressStage -Stage 'push' -Status $script:pipelineStatus -Route $ProgressRoute -PushState 'revealing' -Percent 99 -SaveNow
    if (-not (Complete-PublishMediaReveal -PartialPath $serverPartialOut -FinalPath $Paths.ServerOut -PublishTransactionId $publishTxn -Context $Context)) {
        Set-ProgressStage -Stage 'push' -Status $script:pipelineStatus -Route $ProgressRoute -PushState 'failed' -Percent $null -SaveNow
        Add-RoundFailureRecord -SourcePath $SourceFile.FullName -Stage "$stageName-reveal" -Reason 'Server partial copy and sidecar write succeeded but final media reveal failed' -Classification 'transient' -SuggestedAction 'Inspect share permissions, antivirus locks, or existing output file locks; the local output is being parked for retry.'
        $parkArgs = @{
            LocalOut = $Paths.LocalOut; ServerOut = $Paths.ServerOut; Route = $Route
            MediaType = $sidecarMediaType
            RouteReasonCode = $RouteReasonCode; RouteReason = $RouteReason
            SourceIdentity = $sourceIdentity; SourceIdentityV2 = $sourceIdentityV2
            SourcePath = $SourceFile.FullName; SourceSize = $SourceFile.Length; SourceMTimeUtc = $sourceMTimeUtc
            PublishTransactionId = $publishTxn; PublishMode = 'retry'
            FolderPolicyMetadata = $folderPolicyMetadata
            RoutePlanMetadata = $routePlanMetadata
        }
        if (-not (Invoke-ParkPendingPushWithTx3gSidecars -SourceFile $SourceFile -ScratchPath $ScratchPath -Tx3gTracks @($Tx3gTracks) -BdpgsTracks @($BdpgsTracks) -MediaOutputPath $Paths.ServerOut -ParkArgs $parkArgs -Context $Context)) {
            Write-Log "${logPrefix}: could not park the verified local output after publish reveal failure; leaving it in place at $($Paths.LocalOut)" "ERROR"
        }
        Restore-PublishSidecarAfterRevealFailure -OutputPath $Paths.ServerOut -BackupPath $publishSidecarBackup -Context $Context
        Remove-PublishPartialMedia -Path $serverPartialOut
        return New-PipelinePublishResult -Ok:$false -DeleteLocalOutput:$false -KeepScratchInput:$false -PublishState 'failed' -PublishMode 'retry' -OutputPath $Paths.LocalOut -Reason 'Final media reveal failed'
    }
    Remove-PublishSidecarBackup -BackupPath $publishSidecarBackup
    if (Get-Command -Name Add-CompletedJobsManifestEntryFromSidecar -ErrorAction SilentlyContinue) {
        Add-CompletedJobsManifestEntryFromSidecar -OutputPath $Paths.ServerOut | Out-Null
    }
    Set-ProgressStage -Stage 'push' -Status $script:pipelineStatus -Route $ProgressRoute -PushState 'complete' -Percent 100 -SaveNow
    Write-OutputSummary -FilePath $Paths.ServerOut -Route $Route
    Clear-SourceFailureState $SourceFile
    Invalidate-ProcessedIndexCache
    Write-Log "$logPrefix complete: $(Split-Path $Paths.ServerOut -Leaf)"
    $serverSize = (Get-Item -LiteralPath $Paths.ServerOut -ErrorAction SilentlyContinue).Length
    return New-PipelinePublishResult -Ok:$true -DeleteLocalOutput:$true -KeepScratchInput:$false -PublishState 'published' -PublishMode 'immediate' -OutputPath $Paths.ServerOut -OutputSizeBytes ([long]$serverSize)
}
