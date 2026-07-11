# Extracted from ops/pipeline/engine/process/dynamic_hdr.ps1. Responsibility: preservation planning and encode decisions

function New-DynamicHdrPreservationPlan {
    [CmdletBinding()]
    param(
        [ValidateSet('encode','remux')] [string] $Route = 'encode',
        [string] $Policy = '',
        [bool] $DoviPresent = $false,
        [int] $DoviProfile = 0,
        [int] $DoviBlCompatId = -1,
        [bool] $DoviElPresent = $false,
        [bool] $Hdr10PlusPresent = $false,
        [bool] $DoviToolAvailable = $false,
        [bool] $Hdr10PlusToolAvailable = $false,
        [bool] $X265DolbyVisionCapable = $false,
        [bool] $X265Hdr10PlusCapable = $false,
        [string] $VideoCodec = '',
        [bool] $UseCpuFallback = $false
    )

    $resolvedPolicy = Resolve-DynamicHdrPolicy -Policy $Policy
    $dynamicPresent = ([bool]$DoviPresent -or [bool]$Hdr10PlusPresent)
    $codecText = if ($VideoCodec) { $VideoCodec.Trim().ToLowerInvariant() } else { '' }
    $usingX265 = ([bool]$UseCpuFallback -or $codecText -in @('libx265','x265'))
    $reasons = [System.Collections.Generic.List[string]]::new()
    $caveats = [System.Collections.Generic.List[string]]::new()
    $requiredArtifacts = [System.Collections.Generic.List[string]]::new()
    $targetDoviProfile = ''
    $canEncodeDoviProfile = $true

    if ($DoviPresent) {
        if ($DoviProfile -eq 7) {
            $targetDoviProfile = '8.1'
            $requiredArtifacts.Add('dovi_rpu_converted_profile_8_1')
            if ($DoviElPresent) { $caveats.Add('dovi profile 7 enhancement layer is not preserved by encode') }
        } elseif ($DoviProfile -eq 8 -and $DoviBlCompatId -eq 1) {
            $targetDoviProfile = '8.1'
            $requiredArtifacts.Add('dovi_rpu_profile_8_1')
        } else {
            $canEncodeDoviProfile = $false
            $reasons.Add("dovi profile $DoviProfile is not supported for encode preservation")
        }
    }
    if ($Hdr10PlusPresent) {
        $requiredArtifacts.Add('hdr10plus_json')
    }

    if (-not $dynamicPresent) {
        return [pscustomobject][ordered]@{
            schema_version       = 'dynamic_hdr_preservation_plan.v1'
            policy               = $resolvedPolicy
            route                = $Route
            action               = 'none'
            recommended_route    = $Route
            can_preserve_encode  = $false
            target_dovi_profile  = $targetDoviProfile
            required_artifacts   = @()
            caveats              = @($caveats.ToArray())
            reasons              = @('no dynamic HDR metadata detected')
        }
    }

    if ($resolvedPolicy -eq 'off') {
        return [pscustomobject][ordered]@{
            schema_version       = 'dynamic_hdr_preservation_plan.v1'
            policy               = $resolvedPolicy
            route                = $Route
            action               = 'off'
            recommended_route    = $Route
            can_preserve_encode  = $false
            target_dovi_profile  = $targetDoviProfile
            required_artifacts   = @($requiredArtifacts.ToArray())
            caveats              = @($caveats.ToArray())
            reasons              = @('dynamic HDR preservation policy is off')
        }
    }

    if ($Route -eq 'remux') {
        return [pscustomobject][ordered]@{
            schema_version       = 'dynamic_hdr_preservation_plan.v1'
            policy               = $resolvedPolicy
            route                = $Route
            action               = 'preserve_by_remux'
            recommended_route    = 'remux'
            can_preserve_encode  = $false
            target_dovi_profile  = $targetDoviProfile
            required_artifacts   = @()
            caveats              = @($caveats.ToArray())
            reasons              = @('remux is expected to preserve in-band dynamic HDR metadata')
        }
    }

    if ($resolvedPolicy -eq 'warn') {
        return [pscustomobject][ordered]@{
            schema_version       = 'dynamic_hdr_preservation_plan.v1'
            policy               = $resolvedPolicy
            route                = $Route
            action               = 'warn_only'
            recommended_route    = 'encode'
            can_preserve_encode  = $false
            target_dovi_profile  = $targetDoviProfile
            required_artifacts   = @($requiredArtifacts.ToArray())
            caveats              = @($caveats.ToArray())
            reasons              = @('warn policy records expected dynamic HDR loss without changing routing')
        }
    }

    if (-not $canEncodeDoviProfile) {
        $action = if ($resolvedPolicy -eq 'preserve_or_review') { 'hold_review' } else { 'prefer_remux' }
        $recommended = if ($resolvedPolicy -eq 'preserve_or_review') { 'review' } else { 'remux' }
        return [pscustomobject][ordered]@{
            schema_version       = 'dynamic_hdr_preservation_plan.v1'
            policy               = $resolvedPolicy
            route                = $Route
            action               = $action
            recommended_route    = $recommended
            can_preserve_encode  = $false
            target_dovi_profile  = $targetDoviProfile
            required_artifacts   = @($requiredArtifacts.ToArray())
            caveats              = @($caveats.ToArray())
            reasons              = @($reasons.ToArray())
        }
    }

    if (-not $usingX265) { $reasons.Add('dynamic HDR encode preservation requires CPU x265') }
    if ($DoviPresent -and -not $DoviToolAvailable) { $reasons.Add('dovi_tool is required for Dolby Vision RPU extraction') }
    if ($DoviPresent -and -not $X265DolbyVisionCapable) { $reasons.Add('x265 Dolby Vision RPU capability is not verified') }
    if ($Hdr10PlusPresent -and -not $Hdr10PlusToolAvailable) { $reasons.Add('hdr10plus_tool is required for HDR10+ metadata extraction') }
    if ($Hdr10PlusPresent -and -not $X265Hdr10PlusCapable) { $reasons.Add('x265 HDR10+ metadata capability is not verified') }

    if ($reasons.Count -gt 0) {
        $action = if ($resolvedPolicy -eq 'preserve_or_review') { 'hold_review' } else { 'prefer_remux' }
        $recommended = if ($resolvedPolicy -eq 'preserve_or_review') { 'review' } else { 'remux' }
        return [pscustomobject][ordered]@{
            schema_version       = 'dynamic_hdr_preservation_plan.v1'
            policy               = $resolvedPolicy
            route                = $Route
            action               = $action
            recommended_route    = $recommended
            can_preserve_encode  = $false
            target_dovi_profile  = $targetDoviProfile
            required_artifacts   = @($requiredArtifacts.ToArray())
            caveats              = @($caveats.ToArray())
            reasons              = @($reasons.ToArray())
        }
    }

    return [pscustomobject][ordered]@{
        schema_version       = 'dynamic_hdr_preservation_plan.v1'
        policy               = $resolvedPolicy
        route                = $Route
        action               = 'preserve_encode'
        recommended_route    = 'encode'
        can_preserve_encode  = $true
        target_dovi_profile  = $targetDoviProfile
        required_artifacts   = @($requiredArtifacts.ToArray())
        caveats              = @($caveats.ToArray())
        reasons              = @('encode preservation prerequisites are satisfied')
    }
}

function Resolve-DynamicHdrEncodePreservationDecision {
    [CmdletBinding()]
    param(
        $Evidence,
        [string] $Policy = '',
        [string] $OutputContainer = 'mkv',
        [string] $VideoCodec = '',
        [bool] $DoviToolAvailable = $false,
        [bool] $Hdr10PlusToolAvailable = $false,
        [bool] $X265DolbyVisionCapable = $false,
        [bool] $X265Hdr10PlusCapable = $false
    )

    $resolvedPolicy = Resolve-DynamicHdrPolicy -Policy $Policy
    if ($null -eq $Evidence) {
        return [pscustomobject][ordered]@{
            schema_version           = 'dynamic_hdr_encode_preservation_decision.v1'
            policy                   = $resolvedPolicy
            route                    = 'encode'
            action                   = 'none'
            recommended_route        = 'encode'
            dynamic_metadata_present = $false
            should_extract           = $false
            should_force_cpu         = $false
            should_attempt_gpu       = $true
            should_prefer_remux      = $false
            should_hold_review       = $false
            output_container         = if ($OutputContainer) { $OutputContainer.Trim().ToLowerInvariant() } else { 'mkv' }
            target_dovi_profile      = ''
            required_artifacts       = @()
            caveats                  = @()
            reasons                  = @('dynamic HDR evidence is not available')
            reason                   = 'dynamic HDR evidence is not available'
            reason_code              = 'dynamic_hdr_evidence_missing'
            error_code               = ''
            evidence_summary         = ''
            preservation_plan        = $null
        }
    }

    $dynamicPresent = [bool](Get-DynamicHdrResultValue -Result $Evidence -Name 'dynamic_metadata_present')
    $doviPresent = [bool](Get-DynamicHdrResultValue -Result $Evidence -Name 'dovi_present')
    $hdr10PlusPresent = [bool](Get-DynamicHdrResultValue -Result $Evidence -Name 'hdr10plus_present')
    $summary = [string](Get-DynamicHdrResultValue -Result $Evidence -Name 'summary')
    $container = if ($OutputContainer) { $OutputContainer.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($container)) { $container = 'mkv' }

    $base = [ordered]@{
        schema_version           = 'dynamic_hdr_encode_preservation_decision.v1'
        policy                   = $resolvedPolicy
        route                    = 'encode'
        action                   = 'none'
        recommended_route        = 'encode'
        dynamic_metadata_present = $dynamicPresent
        should_extract           = $false
        should_force_cpu         = $false
        should_attempt_gpu       = $true
        should_prefer_remux      = $false
        should_hold_review       = $false
        output_container         = $container
        target_dovi_profile      = ''
        required_artifacts       = @()
        caveats                  = @()
        reasons                  = @()
        reason                   = ''
        reason_code              = ''
        error_code               = ''
        evidence_summary         = $summary
        preservation_plan        = $null
    }

    if (-not $dynamicPresent) {
        $base.reason = 'no dynamic HDR metadata detected'
        $base.reason_code = 'no_dynamic_hdr_metadata'
        $base.reasons = @($base.reason)
        return [pscustomobject]$base
    }

    if ($resolvedPolicy -eq 'off') {
        $base.action = 'off'
        $base.reason = 'dynamic HDR preservation policy is off'
        $base.reason_code = 'dynamic_hdr_policy_off'
        $base.reasons = @($base.reason)
        return [pscustomobject]$base
    }

    if ($resolvedPolicy -eq 'warn') {
        $base.action = 'warn_only'
        $base.reason = 'warn policy records expected dynamic HDR loss without changing routing'
        $base.reason_code = 'dynamic_hdr_warn_only'
        $base.reasons = @($base.reason)
        return [pscustomobject]$base
    }

    if ($container -ne 'mkv') {
        $base.action = if ($resolvedPolicy -eq 'preserve_or_review') { 'hold_review' } else { 'prefer_remux' }
        $base.recommended_route = if ($resolvedPolicy -eq 'preserve_or_review') { 'review' } else { 'remux' }
        $base.should_hold_review = ($base.action -eq 'hold_review')
        $base.should_prefer_remux = ($base.action -eq 'prefer_remux')
        $base.reason = "dynamic HDR encode preservation requires MKV output; configured container is '$container'"
        $base.reason_code = 'dynamic_hdr_output_container_unsupported'
        $base.error_code = 'DYNAMIC_HDR_UNPRESERVABLE'
        $base.reasons = @($base.reason)
        return [pscustomobject]$base
    }

    $plan = New-DynamicHdrPreservationPlan `
        -Route 'encode' `
        -Policy $resolvedPolicy `
        -DoviPresent:$doviPresent `
        -DoviProfile ([int](Get-DynamicHdrResultValue -Result $Evidence -Name 'dovi_profile')) `
        -DoviBlCompatId ([int](Get-DynamicHdrResultValue -Result $Evidence -Name 'dovi_bl_compat_id')) `
        -DoviElPresent:([bool](Get-DynamicHdrResultValue -Result $Evidence -Name 'dovi_el_present')) `
        -Hdr10PlusPresent:$hdr10PlusPresent `
        -DoviToolAvailable:$DoviToolAvailable `
        -Hdr10PlusToolAvailable:$Hdr10PlusToolAvailable `
        -X265DolbyVisionCapable:$X265DolbyVisionCapable `
        -X265Hdr10PlusCapable:$X265Hdr10PlusCapable `
        -VideoCodec $VideoCodec `
        -UseCpuFallback:$true

    $base.preservation_plan = $plan
    $base.action = [string]$plan.action
    $base.recommended_route = [string]$plan.recommended_route
    $base.target_dovi_profile = [string]$plan.target_dovi_profile
    $base.required_artifacts = @($plan.required_artifacts)
    $base.caveats = @($plan.caveats)
    $base.reasons = @($plan.reasons)
    $base.reason = (@($plan.reasons) -join '; ')

    switch ([string]$plan.action) {
        'preserve_encode' {
            $base.should_extract = $true
            $base.should_force_cpu = $true
            $base.should_attempt_gpu = $false
            $base.reason_code = 'dynamic_hdr_preserve_encode_cpu'
        }
        'prefer_remux' {
            $base.should_prefer_remux = $true
            $base.reason_code = 'dynamic_hdr_prefer_remux'
        }
        'hold_review' {
            $base.should_hold_review = $true
            $base.reason_code = 'dynamic_hdr_hold_review'
            $base.error_code = 'DYNAMIC_HDR_UNPRESERVABLE'
        }
        default {
            $base.reason_code = "dynamic_hdr_$([string]$plan.action)"
        }
    }

    return [pscustomobject]$base
}
