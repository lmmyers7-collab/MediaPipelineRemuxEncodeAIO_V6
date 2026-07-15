# Extracted from ops/pipeline/entrypoints/Invoke-RerunCsv.ps1. Responsibility: destination planning, staging, and produced-output resolution

function Resolve-RerunFinalOutputPathFromRow {
    param(
        $Row,
        [string]$FallbackPath,
        [string]$SourcePath = '',
        [switch]$UseSourcePathDestination
    )
    if ($UseSourcePathDestination) {
        return [pscustomobject]@{
            Path = $SourcePath
            Source = 'source_path'
            SourceField = 'source_path'
        }
    }
    $candidateFields = @(
        'plex_planned_path',
        'PlexPlannedPath',
        'planned_final_path',
        'PlannedFinalPath',
        'final_output_path',
        'FinalOutputPath',
        'server_out',
        'ServerOut',
        'completed_output_path',
        'CompletedOutputPath',
        'completed_path',
        'CompletedPath',
        'PlannedOutputPath',
        'planned_output_path',
        'OutputPath',
        'output_path'
    )
    foreach ($field in $candidateFields) {
        $text = Get-RerunValue -Row $Row -Names @($field) -Default ''
        if ([string]::IsNullOrWhiteSpace($text)) { continue }
        $resolved = Resolve-RerunPath $text
        if ([string]::IsNullOrWhiteSpace($resolved)) { continue }
        return [pscustomobject]@{
            Path = $resolved
            Source = 'csv_completed_output'
            SourceField = $field
        }
    }
    return [pscustomobject]@{
        Path = $FallbackPath
        Source = 'computed'
        SourceField = ''
    }
}

function Set-RerunPlanningFailure {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string]$Reason,
        [Parameter(Mandatory)] [string]$ReasonCode,
        [string]$Next = 'Correct the planning evidence and start a new correlated rerun.'
    )
    Set-RerunPlanLifecycle -Plan $Plan -State 'failed' -Status 'failed' -What 'CSV rerun planning rejected the row.' -Why $Reason -Next $Next -ReasonCode $ReasonCode -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction $Next
}

function Resolve-RerunPlans {
    param(
        [array]$Rows,
        [hashtable]$Config,
        [string]$StageRoot,
        [string]$OutputRoot,
        [string]$FinalOutputRoot,
        [string]$FfprobePath,
        [int]$RowIndexOffset = 0
    )

    $stageMoviesRoot = Join-Path $StageRoot 'Movies'
    $stageTvRoot = Join-Path $StageRoot 'TV'
    $plans = [System.Collections.Generic.List[object]]::new()
    $destinationKeys = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

    $rowIndex = $RowIndexOffset - 1
    foreach ($row in $Rows) {
        $rowIndex += 1
        $enabled = ConvertTo-RerunBool (Get-RerunValue -Row $row -Names @('enabled','rerun_enabled','Enabled') -Default 'true') $true
        if (-not $enabled) { continue }

        $sourceText = Get-RerunValue -Row $row -Names @('source_path','Path','SourcePath') -Default ''
        $sourcePath = Resolve-RerunSourcePath $sourceText
        $rowStageOverride = Normalize-RerunChoiceValue (Get-RerunValue -Row $row -Names @('stage_mode','StageMode') -Default '')
        $rowOriginalOverride = Normalize-RerunChoiceValue (Get-RerunValue -Row $row -Names @('post_success_original','original_mode','OriginalMode') -Default '')
        $rowReturnOverride = Normalize-RerunChoiceValue (Get-RerunValue -Row $row -Names @('return_mode','ReturnMode') -Default '')
        $stageMode = Resolve-RerunChoice -Row $row -Names @('stage_mode','StageMode') -Default $DefaultStageMode -Allowed @('copy','move')
        $originalMode = Resolve-RerunChoice -Row $row -Names @('post_success_original','original_mode','OriginalMode') -Default $DefaultOriginalMode -Allowed @('keep','delete')
        $returnMode = Resolve-RerunChoice -Row $row -Names @('return_mode','ReturnMode') -Default $DefaultReturnMode -Allowed @('park','pending_publish','publish_non_overlap','replace_original')

        $plan = [ordered]@{
            row_index = $rowIndex
            source_path = if ([string]::IsNullOrWhiteSpace($sourcePath)) { $sourceText } else { $sourcePath }
            media_kind = ''
            stage_mode = $stageMode
            original_mode = $originalMode
            return_mode = $returnMode
            stage_path = ''
            planned_output_path = ''
            final_output_path = ''
            final_output_source = 'computed'
            final_output_source_field = ''
            final_output_root = ''
            verified_output_path = ''
            pending_publish_payload_path = ''
            pending_publish_manifest_path = ''
            published_path = ''
            replaced_final_hold_path = ''
            original_action = ''
            original_held_path = ''
            original_cleanup_ready = $false
            auto_destination_policy = ''
            auto_destination_decision = ''
            auto_destination_issue_count = 0
            auto_destination_issues = @()
            pipeline_sidecar_publish = ''
            pipeline_sidecar_path = ''
            published_sidecar_paths = @()
            replaced_sidecar_hold_paths = @()
            completed_manifest_path = ''
            completed_manifest_append = ''
            source_overwrite_confirmed = $false
            staged_input_cleanup = ''
            status = 'pending'
            lifecycle_state = 'pending'
            transition_sequence = 0
            timeline = @()
            reason = ''
            reason_code = ''
            failure_code = ''
            operator_message = ''
            retryable = $false
            attempt_count = 0
            max_attempts = 0
            first_failure_at = ''
            last_failure_at = ''
            next_retry_at = ''
            last_error = ''
            automatic_next_action = 'Stage the source into isolated scratch.'
            operator_action_required = $false
            available_operator_action = ''
            stage_attempt_id = ''
            stage_attempt_count = 0
            staged_at = ''
            source_size = $null
            source_mtime_utc = ''
            source_identity_v2 = Get-RerunValue -Row $row -Names @('source_identity_v2','SourceIdentityV2') -Default ''
            planned_source_identity_v2 = ''
            staged_source_identity_v2 = ''
            source_content_sha256 = Get-RerunValue -Row $row -Names @('source_content_sha256','SourceContentSha256') -Default ''
            planned_source_content_sha256 = ''
            staged_source_content_sha256 = ''
            source_content_sha256_algorithm = Get-RerunValue -Row $row -Names @('source_content_sha256_algorithm','SourceContentSha256Algorithm') -Default ''
            source_root = ''
            nested_launch_count = 0
            nested_launch_id = ''
            audit_issue_codes = Get-RerunValue -Row $row -Names @('audit_issue_codes','IssueCodes','NonSidecarIssueCodes','PrimaryIssueCode') -Default ''
            queue_item = $null
        }
        Add-RerunLifecycleTransition -Target $plan -State 'accepted' -What 'The CSV row was accepted for source classification.' -Why 'The row is enabled and retains its original CSV row index.' -Next 'Classify source reachability and full identity before staging.' -ReasonCode 'row_accepted'
        $plan.status = 'pending'

        if ([string]::IsNullOrWhiteSpace($sourceText)) {
            Set-RerunPlanningFailure -Plan $plan -Reason 'missing source_path' -ReasonCode 'source_missing'
            $plans.Add([pscustomobject]$plan)
            continue
        }
        if ([string]::IsNullOrWhiteSpace($sourcePath)) {
            Set-RerunPlanningFailure -Plan $plan -Reason "relative source_path: $sourceText" -ReasonCode 'source_missing'
            $plans.Add([pscustomobject]$plan)
            continue
        }
        $expectedSize = $null
        $expectedSizeText = Get-RerunValue -Row $row -Names @('source_size','SourceSizeBytes','SizeBytes') -Default ''
        if ($expectedSizeText -match '^\d+$') { $expectedSize = [long]$expectedSizeText }
        $expectedMtime = Get-RerunValue -Row $row -Names @('source_mtime_utc','SourceLastWriteUtc','LastWriteTimeUtc') -Default ''
        $sourceContentSha256 = ([string]$plan.source_content_sha256).Trim()
        $sourceContentSha256Algorithm = ([string]$plan.source_content_sha256_algorithm).Trim()
        $hasSuppliedStrongIdentity = (
            -not [string]::IsNullOrWhiteSpace($sourceContentSha256) -or
            -not [string]::IsNullOrWhiteSpace($sourceContentSha256Algorithm)
        )
        if ($hasSuppliedStrongIdentity -and (
            $sourceContentSha256 -notmatch '^[A-Fa-f0-9]{64}$' -or
            $sourceContentSha256Algorithm -cne 'sha256-full-file'
        )) {
            $reasonCode = if ($sourceContentSha256 -notmatch '^[A-Fa-f0-9]{64}$') { 'source_content_sha256_missing' } else { 'source_content_sha256_algorithm_invalid' }
            $reason = if ($reasonCode -eq 'source_content_sha256_missing') {
                'Supplied full-content identity evidence has no valid 64-hex source_content_sha256.'
            } else {
                $algorithmDisplay = if ([string]::IsNullOrWhiteSpace($sourceContentSha256Algorithm)) { '(missing)' } else { $sourceContentSha256Algorithm }
                "Supplied source_content_sha256 declares $algorithmDisplay instead of sha256-full-file."
            }
            Set-RerunPlanLifecycle -Plan $plan -State 'review' -Status 'review' -What 'Supplied strong source identity is not authoritative.' -Why $reason -Next 'Regenerate source metadata with a full-file SHA-256 before retrying.' -ReasonCode $reasonCode -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Regenerate and review the source full-content identity.'
            $plans.Add([pscustomobject]$plan)
            continue
        }
        $configuredSourceRoot = Resolve-RerunConfiguredSourceRoot -Config $Config -SourcePath $sourcePath
        $sourceHealth = Get-RerunSourceHealth `
            -SourcePath $sourcePath `
            -ExpectedIdentityV2 ([string]$plan.source_identity_v2) `
            -ExpectedContentSha256 ([string]$plan.source_content_sha256) `
            -ExpectedSize $expectedSize `
            -ExpectedMtimeUtc $expectedMtime `
            -ConfiguredRootPath $configuredSourceRoot `
            -FfprobePath $FfprobePath
        $plan.source_root = [string]$sourceHealth.RootPath
        if (-not $sourceHealth.Available) {
            if (
                $sourceHealth.Code -in @('source_location_unavailable','source_access_failed') -and
                [string]$plan.source_content_sha256 -match '^[A-Fa-f0-9]{64}$' -and
                [string]$plan.source_content_sha256_algorithm -ceq 'sha256-full-file'
            ) {
                Set-RerunPlanLifecycle -Plan $plan -State 'waiting' -Status 'waiting' -What 'Source access is temporarily unavailable.' -Why $sourceHealth.Message -Next 'Retry with bounded backoff and verify the sampled fingerprint plus full-content SHA-256 before staging.' -ReasonCode ([string]$sourceHealth.Code) -Retryable $true -OperatorActionRequired $false -AvailableOperatorAction 'Wait or request Retry now; credentials or permissions may require operator correction.'
            } elseif ($sourceHealth.Code -eq 'source_identity_changed') {
                Set-RerunPlanLifecycle -Plan $plan -State 'review' -Status 'review' -What 'Source identity changed after the CSV evidence was captured.' -Why $sourceHealth.Message -Next 'Review the source identity; automatic staging is blocked.' -ReasonCode 'source_identity_changed' -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review the changed source before retrying.'
            } elseif ($sourceHealth.Code -in @('source_location_unavailable','source_access_failed')) {
                Set-RerunPlanLifecycle -Plan $plan -State 'review' -Status 'review' -What 'Automatic source recovery is not provable.' -Why "$($sourceHealth.Message) The CSV row has no valid source_content_sha256 evidence." -Next 'Restore source access and review its full-content identity before retrying.' -ReasonCode 'source_content_sha256_missing' -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review full source identity and access before retrying.'
            } else {
                $legacyReason = if ($sourceHealth.Code -eq 'source_missing') { "source file not found: $sourceText" } else { $sourceHealth.Message }
                Set-RerunPlanLifecycle -Plan $plan -State 'failed' -Status 'failed' -What 'Source validation failed.' -Why $legacyReason -Next 'Correct the source path or access failure before retrying.' -ReasonCode ([string]$sourceHealth.Code) -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Correct the source problem and create a new rerun request.'
            }
            $plans.Add([pscustomobject]$plan)
            continue
        }
        $unsafePolicy = [System.Collections.Generic.List[string]]::new()
        if (-not [string]::IsNullOrWhiteSpace($rowStageOverride) -and $rowStageOverride -ne 'copy') {
            $unsafePolicy.Add("stage_mode=$rowStageOverride")
        }
        if (-not [string]::IsNullOrWhiteSpace($rowOriginalOverride) -and $rowOriginalOverride -ne 'keep') {
            $unsafePolicy.Add("post_success_original=$rowOriginalOverride")
        }
        if (-not [string]::IsNullOrWhiteSpace($rowReturnOverride) -and $rowReturnOverride -ne 'park') {
            $unsafePolicy.Add("return_mode=$rowReturnOverride")
        }
        if ($unsafePolicy.Count -gt 0) {
            Set-RerunPlanningFailure -Plan $plan -Reason "source-mutating or in-place CSV rerun policy is disabled: $($unsafePolicy -join ', ')" -ReasonCode 'unsafe_rerun_policy'
            $plans.Add([pscustomobject]$plan)
            continue
        }
        $stageMode = 'copy'
        $originalMode = 'keep'
        $returnMode = $DefaultReturnMode
        $plan.stage_mode = $stageMode
        $plan.original_mode = $originalMode
        $plan.return_mode = $returnMode
        if ($returnMode -ne $DefaultReturnMode) {
            Set-RerunPlanningFailure -Plan $plan -Reason "mixed return_mode values are not supported in one rerun batch; row=$returnMode batch=$DefaultReturnMode" -ReasonCode 'mixed_return_mode'
            $plans.Add([pscustomobject]$plan)
            continue
        }

        $fileInfo = $sourceHealth.FileInfo
        if (-not (Test-RerunValidMediaExtension $fileInfo.FullName)) {
            $extension = $fileInfo.Extension
            if ([string]::IsNullOrWhiteSpace($extension)) { $extension = '(none)' }
            Set-RerunPlanningFailure -Plan $plan -Reason "invalid media extension: $extension" -ReasonCode 'invalid_media_extension'
            $plans.Add([pscustomobject]$plan)
            continue
        }
        $plan.source_size = [long]$fileInfo.Length
        $plan.source_mtime_utc = $fileInfo.LastWriteTimeUtc.ToString('o')
        $plan.source_identity_v2 = [string]$sourceHealth.IdentityV2
        $plan.planned_source_identity_v2 = [string]$sourceHealth.IdentityV2
        $plan.source_content_sha256 = [string]$sourceHealth.ContentSha256
        $plan.planned_source_content_sha256 = [string]$sourceHealth.ContentSha256
        $plan.source_content_sha256_algorithm = 'sha256-full-file'

        $kind = Get-RerunMediaKind -Row $row -Path $sourcePath
        $plan.media_kind = $kind
        $extension = $fileInfo.Extension
        $effectiveFinalOutputRoot = Get-RerunEffectiveFinalOutputRoot -Config $Config -SourcePath $sourcePath -FallbackRoot $FinalOutputRoot
        $plan.final_output_root = $effectiveFinalOutputRoot
        if ($kind -eq 'TV') {
            $libraryEvidence = Get-RerunLibraryProfileEvidenceForPath -Config $Config -SourcePath $sourcePath -MediaKind $kind
            $tvInfo = Get-TVInfoFromFile `
                -file $fileInfo `
                -SourceRootPath ([string]$libraryEvidence['source_root']) `
                -LibraryName ([string]$libraryEvidence['library_name']) `
                -LibraryId ([string]$libraryEvidence['library_id']) `
                -LibraryDesignation ([string]$libraryEvidence['designation'])
            if (-not $tvInfo.IsReliable) {
                Set-RerunPlanningFailure -Plan $plan -Reason "TV parse failed: $($tvInfo.ParseError)" -ReasonCode 'tv_parse_failed'
                $plans.Add([pscustomobject]$plan)
                continue
            }
            $stagePlan = New-PlexDestinationPlan -MediaKind 'TV' -File $fileInfo -TvInfo $tvInfo -OriginalName $tvInfo.OriginalName -Extension $extension
            $outputPlan = New-PlexDestinationPlan -MediaKind 'TV' -File $fileInfo -TvInfo $tvInfo -OriginalName $tvInfo.OriginalName -Extension ([string]$Config['OutputContainer']) -IncludeLibraryFolder:([bool]$Config['CreateTVSubfolder'])
            $plan.stage_path = Join-Path $stageTvRoot $stagePlan.RelativePath
            $plan.planned_output_path = Join-Path $OutputRoot $outputPlan.RelativePath
            $plan.final_output_path = Join-Path $effectiveFinalOutputRoot $outputPlan.RelativePath
        } else {
            $stagePlan = New-PlexDestinationPlan -MediaKind 'Movie' -File $fileInfo -OriginalName $fileInfo.Name -Extension $extension
            $outputPlan = New-PlexDestinationPlan -MediaKind 'Movie' -File $fileInfo -OriginalName $fileInfo.Name -Extension ([string]$Config['OutputContainer'])
            $plan.stage_path = Join-Path $stageMoviesRoot $stagePlan.RelativePath
            $plan.planned_output_path = Join-Path $OutputRoot $outputPlan.RelativePath
            $plan.final_output_path = Join-Path $effectiveFinalOutputRoot $outputPlan.RelativePath
        }

        $sourcePathDestinationRequested = (
            $ConfirmSourceOverwrite -and
            (
                $DestinationMode -in @('auto_replace_clean_else_pending_review','publish_replace_final') -or
                ($DestinationMode -eq 'pending_publish' -and $CollisionPolicy -eq 'replace_final')
            )
        )
        $finalOutputResolution = Resolve-RerunFinalOutputPathFromRow `
            -Row $row `
            -FallbackPath ([string]$plan.final_output_path) `
            -SourcePath ([string]$plan.source_path) `
            -UseSourcePathDestination:$sourcePathDestinationRequested
        if (-not [string]::IsNullOrWhiteSpace([string]$finalOutputResolution.Path)) {
            $plan.final_output_path = [string]$finalOutputResolution.Path
            $plan.final_output_source = [string]$finalOutputResolution.Source
            $plan.final_output_source_field = [string]$finalOutputResolution.SourceField
        }

        $sourceKey = Get-RerunNormalizedPathKey -Path ([string]$plan.source_path)
        $finalKey = Get-RerunNormalizedPathKey -Path ([string]$plan.final_output_path)
        $finalReplaceRequested = ($DestinationMode -in @('auto_replace_clean_else_pending_review','publish_replace_final') -or ($DestinationMode -eq 'pending_publish' -and $CollisionPolicy -eq 'replace_final'))
        if ($finalReplaceRequested -and -not [string]::IsNullOrWhiteSpace($sourceKey) -and $sourceKey -eq $finalKey) {
            if (-not $ConfirmSourceOverwrite) {
                Set-RerunPlanningFailure -Plan $plan -Reason 'final output resolves to source_path; set confirm_source_overwrite=true to allow CSV rerun source overwrite' -ReasonCode 'source_overwrite_confirmation_required'
                $plans.Add([pscustomobject]$plan)
                continue
            }
            $plan.source_overwrite_confirmed = $true
        }

        $rootViolation = Get-RerunFinalOutputRootViolation `
            -FinalOutputPath ([string]$plan.final_output_path) `
            -SourcePath ([string]$plan.source_path) `
            -EffectiveRoot ([string]$plan.final_output_root) `
            -SourceField ([string]$plan.final_output_source_field) `
            -SourceOverwriteConfirmed ([bool]$plan.source_overwrite_confirmed)
        if (-not [string]::IsNullOrWhiteSpace($rootViolation)) {
            Set-RerunPlanningFailure -Plan $plan -Reason $rootViolation -ReasonCode 'final_output_root_violation'
            $plans.Add([pscustomobject]$plan)
            continue
        }

        $destinationKey = ([string]$plan.planned_output_path).ToLowerInvariant()
        if (-not $destinationKeys.Add($destinationKey)) {
            Set-RerunPlanningFailure -Plan $plan -Reason "duplicate planned output path in CSV: $($plan.planned_output_path)" -ReasonCode 'duplicate_planned_output'
        }
        $queueMediaKind = ([string]$kind).ToLowerInvariant()
        $queueItem = New-MediaQueueItem `
            -File $fileInfo `
            -MediaKind $queueMediaKind `
            -QueueSource 'csv_rerun' `
            -SourcePath $sourcePath `
            -Metadata @{
                stage_path = [string]$plan.stage_path
                planned_output_path = [string]$plan.planned_output_path
                final_output_path = [string]$plan.final_output_path
                final_output_source = [string]$plan.final_output_source
                final_output_source_field = [string]$plan.final_output_source_field
                final_output_root = [string]$plan.final_output_root
                stage_mode = [string]$plan.stage_mode
                original_mode = [string]$plan.original_mode
                return_mode = [string]$plan.return_mode
                status = [string]$plan.status
                audit_issue_codes = [string]$plan.audit_issue_codes
            }
        $plan.queue_item = ConvertTo-MediaQueueItemRecord -QueueItem $queueItem
        $plans.Add([pscustomobject]$plan)
    }
    return @($plans)
}

function Merge-RerunReplannedPlan {
    param([Parameter(Mandatory)] $Plan, [Parameter(Mandatory)] $Replanned)
    $preserved = @{}
    foreach ($name in @(
        'timeline','transition_sequence','attempt_count','max_attempts','first_failure_at','last_failure_at',
        'next_retry_at','last_error','stage_attempt_count','stage_attempt_id'
    )) {
        $preserved[$name] = Get-RerunRecoveryValue -Object $Plan -Name $name -Default $null
    }
    foreach ($property in @($Replanned.PSObject.Properties)) {
        Set-RerunRecoveryValue -Object $Plan -Name $property.Name -Value $property.Value
    }
    foreach ($name in $preserved.Keys) {
        if ($null -ne $preserved[$name]) { Set-RerunRecoveryValue -Object $Plan -Name $name -Value $preserved[$name] }
    }
    Set-RerunRecoveryValue -Object $Plan -Name 'status' -Value 'pending'
    Add-RerunLifecycleTransition -Target $Plan -State 'accepted' -What 'Recovered source evidence produced a fresh accepted plan.' -Why 'The source reconnected with the expected sampled fingerprint and full-content SHA-256, and destination planning remained safe.' -Next 'Stage the source through a new attempt-scoped scratch copy.' -ReasonCode 'source_reconnected'
}

function Invoke-RerunStagePlans {
    param(
        [array]$Plans,
        [hashtable]$Config,
        [string]$StageRoot,
        [string]$OutputRoot,
        [string]$FinalOutputRoot,
        [string]$FfprobePath = '',
        [ValidateRange(1, 20)] [int]$MaxAttempts = 3,
        [int[]]$BackoffSeconds = @(5, 15, 45),
        $Manifest = $null,
        [string]$ManifestPath = '',
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$ScratchTrustRoot,
        [scriptblock]$SleepAction = { param([int]$Seconds) if ($Seconds -gt 0) { Start-Sleep -Seconds $Seconds } }
    )
    $persist = ($null -ne $Manifest -and -not [string]::IsNullOrWhiteSpace($ManifestPath))
    Assert-RerunScratchTrustAnchor -Path $ScratchTrustRoot | Out-Null
    Assert-RerunScratchPathBoundary -Path $StageRoot -Root $ScratchTrustRoot -AllowMissingLeaf | Out-Null
    if (-not (Test-Path -LiteralPath $StageRoot -PathType Container)) {
        New-RerunScratchDirectorySafe -Path $StageRoot -ScratchTrustRoot $ScratchTrustRoot | Out-Null
    }
    Assert-RerunScratchPathBoundary -Path $StageRoot -Root $ScratchTrustRoot | Out-Null
    $orderedPlans = Get-RerunSourceWorkOrder -Plans @($Plans | Where-Object { [string]$_.status -in @('pending','waiting','retry_scheduled','staging') })
    foreach ($plan in $orderedPlans) {
        if ([string]$plan.status -in @('waiting','retry_scheduled')) {
            $sourceReady = Invoke-RerunSourceAvailabilityRecovery -Plan $plan -MaxAttempts $MaxAttempts -BackoffSeconds $BackoffSeconds -FfprobePath $FfprobePath -SleepAction $SleepAction -Manifest $Manifest -ManifestPath $ManifestPath
            if (-not $sourceReady.Ready) { continue }

            if ([string]::IsNullOrWhiteSpace([string]$plan.stage_path)) {
                $rowIndex = [int](Get-RerunRecoveryValue -Object $plan -Name 'row_index' -Default 0)
                $sourceRow = $null
                if ($script:RerunSourceRowsByIndex -and $script:RerunSourceRowsByIndex.ContainsKey($rowIndex)) {
                    $sourceRow = $script:RerunSourceRowsByIndex[$rowIndex]
                }
                if ($null -eq $sourceRow) {
                    Set-RerunPlanLifecycle -Plan $plan -State 'review' -Status 'review' -What 'Recovered source could not be replanned.' -Why 'The original CSV row is unavailable in the current execution.' -Next 'Review the row and start a new correlated rerun.' -ReasonCode 'rerun_resume_evidence_missing' -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review and start a new rerun.' -Manifest $Manifest -ManifestPath $ManifestPath -Persist:$persist
                    continue
                }
                $replanned = @(Resolve-RerunPlans -Rows @($sourceRow) -Config $Config -StageRoot $StageRoot -OutputRoot $OutputRoot -FinalOutputRoot $FinalOutputRoot -FfprobePath $FfprobePath -RowIndexOffset $rowIndex)
                if ($replanned.Count -ne 1 -or [string]$replanned[0].status -ne 'pending') {
                    $reason = if ($replanned.Count -eq 1) { [string]$replanned[0].reason } else { 'Recovered source produced no unique plan.' }
                    Set-RerunPlanLifecycle -Plan $plan -State 'review' -Status 'review' -What 'Recovered source replanning was not safe.' -Why $reason -Next 'Review the row before retrying.' -ReasonCode 'rerun_resume_replan_failed' -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review the recovered source plan.' -Manifest $Manifest -ManifestPath $ManifestPath -Persist:$persist
                    continue
                }
                Merge-RerunReplannedPlan -Plan $plan -Replanned $replanned[0]
                if ($persist) { Write-RerunManifest -Path $ManifestPath -Payload $Manifest }
            }
        }

        $nextStageAttempt = [math]::Max(1, ([int](Get-RerunRecoveryValue -Object $plan -Name 'stage_attempt_count' -Default 0)) + 1)
        if ($nextStageAttempt -gt $MaxAttempts) {
            Set-RerunRecoveryValue -Object $plan -Name 'next_retry_at' -Value ''
            Set-RerunPlanLifecycle -Plan $plan -State 'retry_exhausted' -Status 'retry_exhausted' -What 'Verified scratch-copy retries were already exhausted before resume.' -Why "The durable stage attempt count reached the configured maximum of $MaxAttempts before a staged file was proven." -Next 'Use the backend recovery action to create a new correlated attempt after reviewing source and scratch evidence.' -ReasonCode 'stage_retry_budget_exhausted' -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review and retry through the backend recovery action.' -Manifest $Manifest -ManifestPath $ManifestPath -Persist:$persist
            continue
        }
        Assert-RerunScratchPathBoundary -Path $StageRoot -Root $ScratchTrustRoot | Out-Null
        for ($stageAttempt = $nextStageAttempt; $stageAttempt -le $MaxAttempts; $stageAttempt++) {
            $sourceReady = Invoke-RerunSourceAvailabilityRecovery -Plan $plan -MaxAttempts $MaxAttempts -BackoffSeconds $BackoffSeconds -FfprobePath $FfprobePath -SleepAction $SleepAction -Manifest $Manifest -ManifestPath $ManifestPath
            if (-not $sourceReady.Ready) { break }

            $stagePath = [string]$plan.stage_path
            if ([string]::IsNullOrWhiteSpace($stagePath)) {
                Set-RerunPlanLifecycle -Plan $plan -State 'review' -Status 'review' -What 'Staging path is unavailable.' -Why 'The recovered plan has no staging destination.' -Next 'Review the row before retrying.' -ReasonCode 'rerun_stage_path_missing' -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review the recovered plan.' -Manifest $Manifest -ManifestPath $ManifestPath -Persist:$persist
                break
            }
            try {
                Assert-RerunScratchPathBoundary -Path $StageRoot -Root $ScratchTrustRoot | Out-Null
                Assert-RerunScratchPathBoundary -Path $stagePath -Root $StageRoot -AllowMissingLeaf | Out-Null
            } catch {
                $boundaryMessage = [string]$_.Exception.Message
                Set-RerunPlanLifecycle -Plan $plan -State 'review' -Status 'review' -What 'Scratch boundary proof rejected the staging path.' -Why $boundaryMessage -Next 'Review the scratch workspace path and remove any junction, symlink, or unprovable component before retrying.' -ReasonCode 'rerun_scratch_boundary_rejected' -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review and correct the scratch workspace boundary.' -Manifest $Manifest -ManifestPath $ManifestPath -Persist:$persist
                break
            }
            if (Test-Path -LiteralPath $stagePath -PathType Leaf) {
                if (Test-RerunStagedPlanEvidence -Plan $plan -BatchScratchRoot $StageRoot -FfprobePath $FfprobePath) {
                    Set-RerunPlanLifecycle -Plan $plan -State 'staged' -Status 'staged' -What 'Existing staged scratch was reverified.' -Why 'Scratch size and full source identity match the planned source.' -Next 'Continue processing from verified scratch.' -ReasonCode 'staged_scratch_verified' -Retryable $false -OperatorActionRequired $false -Manifest $Manifest -ManifestPath $ManifestPath -Persist:$persist
                } else {
                    Set-RerunPlanLifecycle -Plan $plan -State 'review' -Status 'review' -What 'Existing staged scratch could not be verified.' -Why "Unverified stage path already exists: $stagePath" -Next 'Review or remove the ambiguous scratch through an explicit recovery action.' -ReasonCode 'staged_scratch_unverified' -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review the ambiguous staged scratch.' -Manifest $Manifest -ManifestPath $ManifestPath -Persist:$persist
                }
                break
            }

            $attemptId = [guid]::NewGuid().ToString('N')
            Set-RerunRecoveryValue -Object $plan -Name 'stage_attempt_id' -Value $attemptId
            Set-RerunRecoveryValue -Object $plan -Name 'stage_attempt_count' -Value $stageAttempt
            Set-RerunPlanLifecycle -Plan $plan -State 'staging' -Status 'staging' -What 'A verified scratch-copy attempt started.' -Why "Stage attempt $stageAttempt of $MaxAttempts is copying from the identity-verified source." -Next 'Verify source and scratch identities before promoting the staged file.' -ReasonCode 'stage_copy_started' -Retryable $true -OperatorActionRequired $false -Manifest $Manifest -ManifestPath $ManifestPath -Persist:$persist
            try {
                $copied = Copy-RerunFileVerified `
                    -Source ([string]$plan.source_path) `
                    -Destination $stagePath `
                    -MaxRetries 1 `
                    -ExpectedSize ([long]$plan.source_size) `
                    -ExpectedMtimeUtc ([string]$plan.source_mtime_utc) `
                    -ExpectedIdentityV2 ([string]$plan.planned_source_identity_v2) `
                    -ExpectedContentSha256 ([string]$plan.planned_source_content_sha256) `
                    -SourceRootPath ([string]$plan.source_root) `
                    -FfprobePath $FfprobePath `
                    -BatchScratchRoot $StageRoot `
                    -ScratchTrustRoot $ScratchTrustRoot `
                    -AttemptId $attemptId
                if (-not $copied) { throw 'stage_copy_failed: verified rerun stage copy failed' }
                Assert-RerunScratchTrustAnchor -Path $ScratchTrustRoot | Out-Null
                Assert-RerunScratchPathBoundary -Path $StageRoot -Root $ScratchTrustRoot | Out-Null
                Assert-RerunScratchPathBoundary -Path $stagePath -Root $StageRoot | Out-Null
                $stageItem = Get-Item -LiteralPath $stagePath -Force -ErrorAction Stop
                if ([long]$stageItem.Length -ne [long]$plan.source_size) {
                    throw 'rerun_scratch_cleanup_ambiguous: staged scratch size changed after verified promotion; evidence was preserved'
                }
                Set-RerunRecoveryValue -Object $plan -Name 'staged_source_identity_v2' -Value ([string]$plan.planned_source_identity_v2)
                Set-RerunRecoveryValue -Object $plan -Name 'staged_source_content_sha256' -Value ([string]$plan.planned_source_content_sha256)
                Set-RerunRecoveryValue -Object $plan -Name 'staged_at' -Value ([datetime]::UtcNow.ToString('o'))
                Set-RerunRecoveryValue -Object $plan -Name 'next_retry_at' -Value ''
                Set-RerunPlanLifecycle -Plan $plan -State 'staged' -Status 'staged' -What 'Scratch copy was verified and atomically promoted.' -Why 'The landed scratch size, sampled fingerprint, and full SHA-256 match the durable source identity validated immediately before copy.' -Next 'Continue processing from verified scratch even if the source later disconnects.' -ReasonCode 'staged_scratch_verified' -Retryable $false -OperatorActionRequired $false -Manifest $Manifest -ManifestPath $ManifestPath -Persist:$persist
                Write-RerunLog ("STAGED {0}: {1}" -f $plan.stage_mode, $plan.source_path)
                break
            } catch {
                $message = [string]$_.Exception.Message
                $code = if ($message -match '^(source_location_unavailable|source_missing|source_access_failed|source_identity_changed|stage_copy_failed):') {
                    [string]$Matches[1]
                } elseif ($message -match '^rerun scratch path boundary (rejected:|helper is unavailable)') {
                    'rerun_scratch_boundary_rejected'
                } elseif ($message -match '^rerun_scratch_cleanup_ambiguous:') {
                    'rerun_scratch_cleanup_ambiguous'
                } else {
                    'stage_copy_failed'
                }
                Write-RerunLog "Rerun stage attempt $stageAttempt failed: $message" 'WARN'
                if ($code -in @('rerun_scratch_boundary_rejected','rerun_scratch_cleanup_ambiguous')) {
                    Set-RerunPlanLifecycle -Plan $plan -State 'review' -Status 'review' -What 'Scratch boundary proof rejected the staging path.' -Why $message -Next 'Review the scratch workspace path and remove any junction, symlink, or unprovable component before retrying.' -ReasonCode $code -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review and correct the scratch workspace boundary.' -Manifest $Manifest -ManifestPath $ManifestPath -Persist:$persist
                    break
                }
                if ($code -eq 'source_identity_changed') {
                    Set-RerunPlanLifecycle -Plan $plan -State 'review' -Status 'review' -What 'Source identity changed during staging.' -Why $message -Next 'Review the changed source; no staged file was accepted.' -ReasonCode $code -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review the changed source before retrying.' -Manifest $Manifest -ManifestPath $ManifestPath -Persist:$persist
                    break
                }
                if ($code -eq 'source_missing') {
                    Set-RerunPlanLifecycle -Plan $plan -State 'failed' -Status 'failed' -What 'Source became unavailable in a non-retryable way during staging.' -Why $message -Next 'Correct the source problem before retrying.' -ReasonCode $code -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Correct the source problem.' -Manifest $Manifest -ManifestPath $ManifestPath -Persist:$persist
                    break
                }
                if ($stageAttempt -ge $MaxAttempts) {
                    Set-RerunRecoveryValue -Object $plan -Name 'next_retry_at' -Value ''
                    Set-RerunPlanLifecycle -Plan $plan -State 'retry_exhausted' -Status 'retry_exhausted' -What 'Verified scratch-copy retries were exhausted.' -Why $message -Next 'Wait for an operator retry after correcting the source or scratch condition.' -ReasonCode $code -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Retry after correcting the staging condition.' -Manifest $Manifest -ManifestPath $ManifestPath -Persist:$persist
                    break
                }
                $delay = Get-RerunRetryDelaySeconds -Attempt $stageAttempt -BackoffSeconds $BackoffSeconds
                $nextRetryAt = [datetime]::UtcNow.AddSeconds($delay).ToString('o')
                Set-RerunRecoveryValue -Object $plan -Name 'next_retry_at' -Value $nextRetryAt
                Set-RerunPlanLifecycle -Plan $plan -State 'retry_scheduled' -Status 'retry_scheduled' -What 'A bounded staging retry was scheduled.' -Why $message -Next "Retry verified staging at $nextRetryAt." -ReasonCode $code -Retryable $true -OperatorActionRequired $false -AvailableOperatorAction 'Wait or request Retry now.' -Manifest $Manifest -ManifestPath $ManifestPath -Persist:$persist
                & $SleepAction $delay
            }
        }
    }
}

function Resolve-RerunProducedOutput {
    param($Plan)

    $plannedOutput = [string]$Plan.planned_output_path
    if (-not [string]::IsNullOrWhiteSpace($plannedOutput) -and (Test-Path -LiteralPath $plannedOutput -PathType Leaf)) {
        return [pscustomobject]@{
            Path = $plannedOutput
            Code = 'RERUN_PLANNED_OUTPUT_VERIFIED'
            OperatorMessage = 'The expected rerun output was verified.'
        }
    }

    # Runtime TV naming can add an episode title that was unavailable to CSV
    # planning. Never infer a replacement by filename alone: accept only one
    # sidecar-backed output whose source identity and staged input match the row.
    $expectedIdentity = [string]$Plan.source_identity_v2
    $expectedStagePath = [string]$Plan.stage_path
    $outputDirectory = Split-Path -Parent $plannedOutput
    $extension = [System.IO.Path]::GetExtension($plannedOutput)
    if (
        [string]::IsNullOrWhiteSpace($expectedIdentity) -or
        [string]::IsNullOrWhiteSpace($expectedStagePath) -or
        [string]::IsNullOrWhiteSpace($outputDirectory) -or
        [string]::IsNullOrWhiteSpace($extension) -or
        -not (Test-Path -LiteralPath $outputDirectory -PathType Container)
    ) {
        return [pscustomobject]@{
            Path = ''
            Code = 'RERUN_OUTPUT_EVIDENCE_MISSING'
            OperatorMessage = 'The rerun output could not be verified because its matching evidence is incomplete. Source media was not changed.'
        }
    }

    $matches = @()
    $candidateCount = 0
    foreach ($candidate in @(Get-ChildItem -LiteralPath $outputDirectory -File -ErrorAction SilentlyContinue)) {
        if (-not $candidate.Extension.Equals($extension, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
        $candidateCount += 1
        $sidecarPath = "$($candidate.FullName).pipeline.json"
        if (-not (Test-Path -LiteralPath $sidecarPath -PathType Leaf)) { continue }
        try {
            $sidecar = Get-Content -LiteralPath $sidecarPath -Raw | ConvertFrom-Json -ErrorAction Stop
        } catch {
            continue
        }
        if (-not ([string]$sidecar.source_identity_v2).Equals($expectedIdentity, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
        if (-not (Test-RerunSamePath -Left ([string]$sidecar.source_path) -Right $expectedStagePath)) { continue }
        if (-not (Test-RerunSamePath -Left ([string]$sidecar.output_path) -Right $candidate.FullName)) { continue }
        $matches += $candidate.FullName
    }

    if ($matches.Count -eq 1) {
        return [pscustomobject]@{
            Path = [string]$matches[0]
            Code = 'RERUN_RUNTIME_NAMED_OUTPUT_RECONCILED'
            OperatorMessage = 'A runtime-named rerun output was verified with matching sidecar evidence.'
        }
    }
    if ($matches.Count -gt 1) {
        $message = 'More than one output matched this rerun item. Nothing was published.'
        Write-RerunLog "RERUN_OUTPUT_AMBIGUOUS: $message Source=$($Plan.source_path)" 'WARN'
        return [pscustomobject]@{
            Path = ''
            Code = 'RERUN_OUTPUT_AMBIGUOUS'
            OperatorMessage = $message
        }
    }
    if ($candidateCount -gt 0) {
        return [pscustomobject]@{
            Path = ''
            Code = 'RERUN_OUTPUT_EVIDENCE_MISSING'
            OperatorMessage = 'A rerun output was found, but its evidence did not match this row. It was left untouched for review.'
        }
    }
    return [pscustomobject]@{
        Path = ''
        Code = 'RERUN_OUTPUT_MISSING'
        OperatorMessage = 'The rerun did not create the expected output. Source media was not changed.'
    }
}

function Complete-RerunPlans {
    param([array]$Plans)
    foreach ($plan in @($Plans | Where-Object { $_.status -in @('staged','processing') })) {
        $plannedOutput = [string]$plan.planned_output_path
        $outputResolution = Resolve-RerunProducedOutput -Plan $plan
        $outPath = [string]$outputResolution.Path
        if ([string]::IsNullOrWhiteSpace($outPath) -or -not (Test-Path -LiteralPath $outPath -PathType Leaf)) {
            $plan.status = 'failed'
            $plan.failure_code = [string]$outputResolution.Code
            $plan.operator_message = [string]$outputResolution.OperatorMessage
            $plan.reason = "$($plan.failure_code): $($plan.operator_message)"
            Write-RerunLog $plan.reason 'WARN'
            continue
        }
        $outItem = Get-Item -LiteralPath $outPath -Force
        if ($outItem.Length -le 0) {
            $plan.status = 'failed'
            $plan.failure_code = 'RERUN_OUTPUT_EMPTY'
            $plan.operator_message = 'The rerun created an empty output file. Source media was not changed.'
            $plan.reason = "$($plan.failure_code): $($plan.operator_message)"
            Write-RerunLog $plan.reason 'WARN'
            continue
        }

        $plan.status = 'complete'
        $plan.verified_output_path = $outPath
        $plan.failure_code = ''
        $plan.operator_message = [string]$outputResolution.OperatorMessage
        $plan.reason = if (Test-RerunSamePath -Left $outPath -Right $plannedOutput) {
            'verified output exists'
        } else {
            'verified runtime-named output exists with matching sidecar source identity'
        }
    }
}
