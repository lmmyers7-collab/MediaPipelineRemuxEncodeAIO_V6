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

function Resolve-RerunPlans {
    param(
        [array]$Rows,
        [hashtable]$Config,
        [string]$StageRoot,
        [string]$OutputRoot,
        [string]$FinalOutputRoot,
        [string]$FfprobePath
    )

    $stageMoviesRoot = Join-Path $StageRoot 'Movies'
    $stageTvRoot = Join-Path $StageRoot 'TV'
    $plans = [System.Collections.Generic.List[object]]::new()
    $destinationKeys = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

    $rowIndex = -1
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
            reason = ''
            failure_code = ''
            operator_message = ''
            source_size = $null
            source_mtime_utc = ''
            source_identity_v2 = Get-RerunValue -Row $row -Names @('source_identity_v2','SourceIdentityV2') -Default ''
            audit_issue_codes = Get-RerunValue -Row $row -Names @('audit_issue_codes','IssueCodes','NonSidecarIssueCodes','PrimaryIssueCode') -Default ''
            queue_item = $null
        }

        if ([string]::IsNullOrWhiteSpace($sourceText)) {
            $plan.status = 'failed'
            $plan.reason = 'missing source_path'
            $plans.Add([pscustomobject]$plan)
            continue
        }
        if ([string]::IsNullOrWhiteSpace($sourcePath)) {
            $plan.status = 'failed'
            $plan.reason = "relative source_path: $sourceText"
            $plans.Add([pscustomobject]$plan)
            continue
        }
        if ([string]::IsNullOrWhiteSpace($sourcePath) -or -not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            $plan.status = 'failed'
            $plan.reason = "source file not found: $sourceText"
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
            $plan.status = 'failed'
            $plan.reason = "source-mutating or in-place CSV rerun policy is disabled: $($unsafePolicy -join ', ')"
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
            $plan.status = 'failed'
            $plan.reason = "mixed return_mode values are not supported in one rerun batch; row=$returnMode batch=$DefaultReturnMode"
            $plans.Add([pscustomobject]$plan)
            continue
        }

        $fileInfo = Get-Item -LiteralPath $sourcePath -Force
        if (-not (Test-RerunValidMediaExtension $fileInfo.FullName)) {
            $extension = $fileInfo.Extension
            if ([string]::IsNullOrWhiteSpace($extension)) { $extension = '(none)' }
            $plan.status = 'failed'
            $plan.reason = "invalid media extension: $extension"
            $plans.Add([pscustomobject]$plan)
            continue
        }
        $plan.source_size = [long]$fileInfo.Length
        $plan.source_mtime_utc = $fileInfo.LastWriteTimeUtc.ToString('o')
        $identityFailure = Test-RerunSourceMatchesCsv -FileInfo $fileInfo -Row $row -FfprobePath $FfprobePath
        if ($identityFailure) {
            $plan.status = 'failed'
            $plan.reason = $identityFailure
            $plans.Add([pscustomobject]$plan)
            continue
        }

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
                $plan.status = 'failed'
                $plan.reason = "TV parse failed: $($tvInfo.ParseError)"
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
                $plan.status = 'failed'
                $plan.reason = 'final output resolves to source_path; set confirm_source_overwrite=true to allow CSV rerun source overwrite'
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
            $plan.status = 'failed'
            $plan.reason = $rootViolation
            $plans.Add([pscustomobject]$plan)
            continue
        }

        $destinationKey = ([string]$plan.planned_output_path).ToLowerInvariant()
        if (-not $destinationKeys.Add($destinationKey)) {
            $plan.status = 'failed'
            $plan.reason = "duplicate planned output path in CSV: $($plan.planned_output_path)"
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

function Invoke-RerunStagePlans {
    param([array]$Plans)
    foreach ($plan in @($Plans | Where-Object { $_.status -eq 'pending' })) {
        try {
            $stageDir = Split-Path -Parent ([string]$plan.stage_path)
            if (-not (Test-Path -LiteralPath $stageDir)) { New-Item -ItemType Directory -Path $stageDir -Force | Out-Null }
            if (Test-Path -LiteralPath ([string]$plan.stage_path)) {
                throw "stage path already exists: $($plan.stage_path)"
            }
            if (-not (Copy-RerunFileVerified -Source ([string]$plan.source_path) -Destination ([string]$plan.stage_path))) {
                throw "verified rerun stage copy failed"
            }
            $plan.status = 'staged'
            Write-RerunLog ("STAGED {0}: {1}" -f $plan.stage_mode, $plan.source_path)
        } catch {
            $plan.status = 'failed'
            $plan.reason = "stage failed: $($_.Exception.Message)"
            Write-RerunLog $plan.reason "ERROR"
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
    foreach ($plan in @($Plans | Where-Object { $_.status -eq 'staged' })) {
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
