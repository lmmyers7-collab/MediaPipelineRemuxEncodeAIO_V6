# ==============================================================================
# ops\pipeline\engine\paths\output_evidence.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\paths\output_path_planning.ps1. Keep function names
# stable; output_path_planning.ps1 dot-sources this file as the public surface.
# ==============================================================================

function Get-MediaPipelineOutputContainerPlanningEvidence {
    param(
        $LibraryOverrides = $null,
        $RuntimeEffectiveSettings = $null,
        [string] $LibraryOutputRoot = '',
        [string] $LibrarySourceRoot = '',
        [string] $DefaultOutputContainer = ''
    )

    $overrideMap = ConvertTo-MediaPipelineProfileMap $LibraryOverrides
    $defaultContainer = if ([string]::IsNullOrWhiteSpace($DefaultOutputContainer)) { [string]$OutputContainer } else { [string]$DefaultOutputContainer }
    $containerValue = $defaultContainer
    $sourceLayer = 'global'
    $overrode = @()
    if ($overrideMap.Contains('OutputContainer')) {
        $containerValue = [string]$overrideMap['OutputContainer']
        $sourceLayer = 'library'
        $overrode = @('global')
    }
    $effectiveValues = [ordered]@{}
    if ($null -ne $RuntimeEffectiveSettings) {
        $effectiveValues = ConvertTo-MediaPipelineProfileMap (Get-MediaPipelineProfileProperty -Profile $RuntimeEffectiveSettings -Name 'effective_values' -Default $null)
    }
    if ($effectiveValues.Contains('OutputContainer')) {
        $entry = $effectiveValues['OutputContainer']
        $containerValue = [string](Get-MediaPipelineProfileProperty -Profile $entry -Name 'value' -Default $containerValue)
        $sourceLayer = [string](Get-MediaPipelineProfileProperty -Profile $entry -Name 'source_layer' -Default $sourceLayer)
        $overrode = @((Get-MediaPipelineProfileProperty -Profile $entry -Name 'overrode' -Default $overrode) | ForEach-Object { [string]$_ })
    }
    $folderFileSupported = ($sourceLayer -in @('folder','file'))

    return [ordered]@{
        schema                                         = 'runtime_consumer_settings.v1'
        consumer                                       = 'container_path_planning'
        diagnostic_only                                = $true
        evidence_source                                = 'path_planning'
        library_output_root                            = [string]$LibraryOutputRoot
        library_source_root                            = [string]$LibrarySourceRoot
        planned_output_root                            = [string]$LibraryOutputRoot
        planned_output_path_available                  = $false
        planned_output_path_note                       = 'Full output path is produced by Get-OutputPaths; this evidence records the selected container/root policy.'
        folder_file_output_container_override_supported = [bool]$folderFileSupported
        warning                                        = if ($folderFileSupported) { '' } else { 'OutputContainer path planning uses global/library state unless a runtime folder/file override is active.' }
        settings                                       = [ordered]@{
            OutputContainer = [ordered]@{
                value           = $containerValue
                source_layer    = $sourceLayer
                overrode        = @($overrode)
                decision_scope  = 'container_path_planning'
                decision_impact = if ($folderFileSupported) { 'sets planned output extension through active runtime overrides' } else { 'sets planned output extension before folder/file layers' }
                consequence     = 'planned output path extension'
                available       = $true
            }
        }
    }
}

function New-MediaPipelineSizeGuardEvidence {
    param(
        $RuntimeEffectiveSettings = $null,
        $SizePolicyResult = $null,
        $RoutePlan = $null
    )

    $sizeKeys = @(
        'SizeGuardMode',
        'EncodeThresholdGB',
        'TVEncodeThresholdGB',
        'MovieRoute1080pTargetSizeGB',
        'MovieRoute1440pTargetSizeGB',
        'MovieRoute4KTargetSizeGB',
        'TVRoute1080pTargetSizeGB',
        'TVRoute1440pTargetSizeGB',
        'TVRoute4KTargetSizeGB',
        'MaxEncodeGrowthPercent',
        'CompatibilityEncodeGrowthPercent'
    )
    $settingsEvidence = if ($null -ne $RuntimeEffectiveSettings) {
        New-MediaPipelineRuntimeConsumerSettingsEvidence `
            -RuntimeEffectiveSettings $RuntimeEffectiveSettings `
            -Consumer 'size_guard' `
            -Keys $sizeKeys `
            -DecisionScope 'post_encode_size_guard' `
            -ActionEvidence 'checked after encode; does not participate in direct-copy bitrate gates' `
            -DecisionImpact ([ordered]@{
                SizeGuardMode = 'post_encode_outcome_policy'
                EncodeThresholdGB = 'output_size_target_budget'
                TVEncodeThresholdGB = 'output_size_target_budget'
                MovieRoute1080pTargetSizeGB = 'output_size_target_budget'
                MovieRoute1440pTargetSizeGB = 'output_size_target_budget'
                MovieRoute4KTargetSizeGB = 'output_size_target_budget'
                TVRoute1080pTargetSizeGB = 'output_size_target_budget'
                TVRoute1440pTargetSizeGB = 'output_size_target_budget'
                TVRoute4KTargetSizeGB = 'output_size_target_budget'
                MaxEncodeGrowthPercent = 'quality_encode_size_tolerance'
                CompatibilityEncodeGrowthPercent = 'compatibility_encode_size_tolerance'
            })
    } else {
        [ordered]@{
            schema          = 'runtime_consumer_settings.v1'
            consumer        = 'size_guard'
            diagnostic_only = $true
            evidence_source = 'runtime_effective_settings.v1'
            action_selected = ''
            action_evidence = 'runtime effective settings unavailable'
            settings        = [ordered]@{}
            unsupported_keys = @()
            ignored_keys     = @()
            warnings         = @('runtime effective settings unavailable')
        }
    }

    $policy = $SizePolicyResult
    if ($null -ne $policy -and $policy.PSObject.Properties['Metadata']) {
        $policy = $policy.Metadata
    }
    $hasPolicy = ($null -ne $policy)
    $mode = if ($hasPolicy) { [string](Get-MediaPipelineProfileProperty -Profile $policy -Name 'mode' -Default '') } else { '' }
    $exceeded = if ($hasPolicy) { [bool](Get-MediaPipelineProfileProperty -Profile $policy -Name 'exceeded' -Default $false) } else { $false }
    $enforced = if ($hasPolicy) { [bool](Get-MediaPipelineProfileProperty -Profile $policy -Name 'enforced' -Default $false) } else { $false }
    $outcome = if (-not $hasPolicy) {
        'not_available'
    } elseif ($exceeded -and $enforced) {
        'block'
    } elseif ($exceeded) {
        'warn'
    } else {
        'pass'
    }
    $strictness = if (-not $hasPolicy) {
        'computed'
    } elseif ($mode -eq 'strict') {
        'hard'
    } elseif ($mode -eq 'off') {
        'advisory'
    } else {
        'advisory'
    }

    $routeIsTV = if ($null -ne $RoutePlan) { [bool](Get-MediaPipelineProfileProperty -Profile $RoutePlan -Name 'IsTV' -Default $false) } else { $false }
    $targetKey = if ($routeIsTV) { 'TVEncodeThresholdGB' } else { 'EncodeThresholdGB' }
    $targetSizeGB = $null
    $settingMap = ConvertTo-MediaPipelineProfileMap $settingsEvidence['settings']
    if ($settingMap.Contains($targetKey)) {
        $targetSizeGB = Get-MediaPipelineProfileProperty -Profile $settingMap[$targetKey] -Name 'value' -Default $null
    }

    return [ordered]@{
        schema                       = 'size_guard_evidence.v1'
        diagnostic_only              = $true
        available                    = $hasPolicy
        mode                         = $mode
        strictness                   = $strictness
        outcome                      = $outcome
        checked_after_encode         = $true
        settings                     = $settingsEvidence
        target_size_key              = $targetKey
        target_size_gb               = $targetSizeGB
        route_threshold_gb           = if ($null -ne $RoutePlan) { Get-MediaPipelineProfileProperty -Profile $RoutePlan -Name 'ThresholdGB' -Default $null } else { $null }
        estimated_bitrate_mbps       = if ($null -ne $RoutePlan) { Get-MediaPipelineProfileProperty -Profile $RoutePlan -Name 'EstimatedBitrateMbps' -Default $null } else { $null }
        bitrate_gate_mbps            = if ($null -ne $RoutePlan) { Get-MediaPipelineProfileProperty -Profile $RoutePlan -Name 'BitrateThresholdMbps' -Default $null } else { $null }
        source_size_bytes            = if ($hasPolicy) { Get-MediaPipelineProfileProperty -Profile $policy -Name 'source_size_bytes' -Default 0L } else { 0L }
        output_size_bytes            = if ($hasPolicy) { Get-MediaPipelineProfileProperty -Profile $policy -Name 'output_size_bytes' -Default 0L } else { 0L }
        growth_percent_used          = if ($hasPolicy) { Get-MediaPipelineProfileProperty -Profile $policy -Name 'max_growth_percent' -Default $null } else { $null }
        limit_ratio                  = if ($hasPolicy) { Get-MediaPipelineProfileProperty -Profile $policy -Name 'limit_ratio' -Default $null } else { $null }
        ratio                        = if ($hasPolicy) { Get-MediaPipelineProfileProperty -Profile $policy -Name 'ratio' -Default $null } else { $null }
        exceeded                     = $exceeded
        enforced                     = $enforced
        route_reason_code            = if ($hasPolicy) { [string](Get-MediaPipelineProfileProperty -Profile $policy -Name 'route_reason_code' -Default '') } else { '' }
        message                      = if ($hasPolicy) { [string](Get-MediaPipelineProfileProperty -Profile $policy -Name 'message' -Default '') } else { 'size guard evidence unavailable before encode output is checked' }
        distinction_note             = 'GB target settings are output size budgets checked after encode; Mbps values are routing bitrate gates used before processing.'
    }
}

function New-MediaPipelinePublishEvidence {
    param(
        $PublishResult = $null,
        [string] $Route = ''
    )

    $hasPublishResult = ($null -ne $PublishResult)
    $publishState = if ($hasPublishResult) { [string](Get-MediaPipelineProfileProperty -Profile $PublishResult -Name 'PublishState' -Default '') } else { '' }
    $publishMode = if ($hasPublishResult) { [string](Get-MediaPipelineProfileProperty -Profile $PublishResult -Name 'PublishMode' -Default '') } else { '' }
    $ok = if ($hasPublishResult) { [bool](Get-MediaPipelineProfileProperty -Profile $PublishResult -Name 'Ok' -Default $false) } else { $false }
    $reason = if ($hasPublishResult) { [string](Get-MediaPipelineProfileProperty -Profile $PublishResult -Name 'Reason' -Default '') } else { '' }
    $deferred = ($publishState -eq 'pending_publish' -or $publishMode -match 'deferred')
    $attempted = ($hasPublishResult -and (-not [string]::IsNullOrWhiteSpace($publishState) -or -not [string]::IsNullOrWhiteSpace($publishMode)))
    $outcome = if (-not $attempted) {
        'not_attempted'
    } elseif ($ok -and $deferred) {
        'deferred'
    } elseif ($ok) {
        'published'
    } else {
        'failed'
    }

    return [ordered]@{
        schema                  = 'publish_evidence.v1'
        diagnostic_only         = $true
        route                   = [string]$Route
        attempted               = $attempted
        allowed                 = ($attempted -and $ok)
        blocked                 = ($attempted -and -not $ok)
        deferred                = $deferred
        outcome                 = $outcome
        publish_state           = $publishState
        publish_mode            = $publishMode
        output_path             = if ($hasPublishResult) { [string](Get-MediaPipelineProfileProperty -Profile $PublishResult -Name 'OutputPath' -Default '') } else { '' }
        output_size_bytes       = if ($hasPublishResult) { [long](Get-MediaPipelineProfileProperty -Profile $PublishResult -Name 'OutputSizeBytes' -Default 0L) } else { 0L }
        reason                  = $reason
        parked_for_output_space = if ($hasPublishResult) { [bool](Get-MediaPipelineProfileProperty -Profile $PublishResult -Name 'ParkedForOutputSpace' -Default $false) } else { $false }
        pending_publish_status  = if ($deferred) { 'pending drain through existing pending-publish flow' } else { '' }
    }
}

function New-MediaPipelineVerificationEvidence {
    param(
        $SizeGuardEvidence = $null,
        $PublishEvidence = $null
    )

    $checks = New-Object System.Collections.Generic.List[string]
    $warnings = New-Object System.Collections.Generic.List[string]
    $blockingFailures = New-Object System.Collections.Generic.List[string]
    if ($null -ne $SizeGuardEvidence -and [bool]$SizeGuardEvidence['available']) {
        [void]$checks.Add('size_guard')
        $sizeOutcome = [string]$SizeGuardEvidence['outcome']
        if ($sizeOutcome -eq 'warn') { [void]$warnings.Add('size_guard_warning') }
        if ($sizeOutcome -eq 'block') { [void]$blockingFailures.Add('size_guard_block') }
    }
    if ($null -ne $PublishEvidence -and [bool]$PublishEvidence['attempted']) {
        [void]$checks.Add('publish_result')
        if ([bool]$PublishEvidence['blocked']) { [void]$blockingFailures.Add('publish_failed_or_blocked') }
        if ([bool]$PublishEvidence['deferred']) { [void]$warnings.Add('publish_deferred_pending_drain') }
    }
    $result = if ($blockingFailures.Count -gt 0) {
        'failed'
    } elseif ($warnings.Count -gt 0) {
        'warning'
    } elseif ($checks.Count -gt 0) {
        'passed'
    } else {
        'not_available'
    }

    return [ordered]@{
        schema            = 'verification_evidence.v1'
        diagnostic_only   = $true
        checks_run        = @($checks)
        result            = $result
        warnings          = @($warnings)
        blocking_failures = @($blockingFailures)
        size_guard_ref    = if ($null -ne $SizeGuardEvidence) { [string]$SizeGuardEvidence['schema'] } else { '' }
        publish_ref       = if ($null -ne $PublishEvidence) { [string]$PublishEvidence['schema'] } else { '' }
        note              = 'Diagnostic summary only; verification, size guard, publish, and drain logic remain owned by existing runtime code.'
    }
}
