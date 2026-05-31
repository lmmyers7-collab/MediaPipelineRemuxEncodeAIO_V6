# Strict validation helpers for Phase 07B pipeline_plan.v1 dry-run records.

function Get-PipelinePlanObjectPropertyNames {
    param($Value)
    if ($null -eq $Value -or $null -eq $Value.PSObject) { return @() }
    return @($Value.PSObject.Properties | ForEach-Object { [string]$_.Name })
}

function Test-PipelinePlanObjectHasProperty {
    param(
        $Value,
        [Parameter(Mandatory)] [string] $Name
    )
    return ((Get-PipelinePlanObjectPropertyNames -Value $Value) -contains $Name)
}

function Get-PipelinePlanProperty {
    param(
        $Value,
        [Parameter(Mandatory)] [string] $Name,
        $Default = $null
    )
    if ($null -eq $Value -or -not (Test-PipelinePlanObjectHasProperty -Value $Value -Name $Name)) {
        return $Default
    }
    return $Value.PSObject.Properties[$Name].Value
}

function Get-PipelinePlanNestedProperty {
    param(
        $Value,
        [Parameter(Mandatory)] [string[]] $Path,
        $Default = $null
    )

    $cursor = $Value
    foreach ($name in $Path) {
        if ($null -eq $cursor -or -not (Test-PipelinePlanObjectHasProperty -Value $cursor -Name $name)) {
            return $Default
        }
        $cursor = $cursor.PSObject.Properties[$name].Value
    }
    if ($null -eq $cursor) { return $Default }
    return $cursor
}

function Assert-PipelinePlanProperties {
    param(
        [Parameter(Mandatory)] $Value,
        [Parameter(Mandatory)] [string] $Path,
        [string[]] $Required = @(),
        [Parameter(Mandatory)] [string[]] $Allowed
    )

    if ($null -eq $Value -or $null -eq $Value.PSObject) {
        throw "PipelinePlan validation failed at ${Path}: expected an object."
    }

    $names = @(Get-PipelinePlanObjectPropertyNames -Value $Value)
    foreach ($requiredName in $Required) {
        if ($names -notcontains $requiredName) {
            throw "PipelinePlan validation failed at ${Path}: missing required property '$requiredName'."
        }
    }
    foreach ($name in $names) {
        if ($Allowed -notcontains $name) {
            throw "PipelinePlan validation failed at ${Path}: unknown property '$name'."
        }
    }
}

function Assert-PipelinePlanEnum {
    param(
        [Parameter(Mandatory)] [string] $Value,
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string[]] $Allowed
    )
    if ($Allowed -notcontains $Value) {
        throw "PipelinePlan validation failed at ${Path}: invalid value '$Value'. Allowed: $($Allowed -join ', ')."
    }
}

function Get-PipelinePlanArray {
    param($Value)
    if ($null -eq $Value) { return @() }
    return @($Value)
}

function Get-PipelinePlanStreamActions {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string] $StreamType
    )
    return @($Plan.streamActions | Where-Object { [string]$_.streamType -eq $StreamType })
}

function Get-PipelinePlanSingleStreamAction {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string] $StreamType
    )
    $matches = @(Get-PipelinePlanStreamActions -Plan $Plan -StreamType $StreamType)
    if ($matches.Count -eq 0) {
        throw "PipelinePlan validation failed: missing '$StreamType' stream action."
    }
    if ($matches.Count -gt 1) {
        throw "PipelinePlan validation failed: expected one '$StreamType' stream action but found $($matches.Count)."
    }
    return $matches[0]
}

function Assert-PipelinePlanValid {
    param([Parameter(Mandatory)] $Plan)

    Assert-PipelinePlanProperties -Value $Plan -Path '$' -Required @(
        'schemaVersion','planId','intent','sourceId','output','routeSummary','streamActions',
        'publishStrategy','commandPlans'
    ) -Allowed @(
        'schemaVersion','planId','intent','sourceId','sourcePath','output','routeSummary',
        'streamActions','reasonSummary','warnings','publishStrategy','verificationRequirements',
        'verificationGuards','verificationResult','publishRequirements',
        'runtimeFallbacks','commandPlans','effectivePresetSnapshot','decisionSnapshot'
    )

    if ([string]$Plan.schemaVersion -ne 'pipeline_plan.v1') {
        throw "PipelinePlan validation failed: unsupported schemaVersion '$($Plan.schemaVersion)'."
    }
    if ([string]$Plan.intent -ne 'dry_run') {
        throw "PipelinePlan validation failed: Phase 07B accepts dry_run plans only."
    }
    Assert-PipelinePlanEnum -Value ([string]$Plan.routeSummary) -Path '$.routeSummary' -Allowed @('COPY','REMUX','ENCODE','REJECT','UNKNOWN')
    if ([string]$Plan.routeSummary -eq 'UNKNOWN') {
        throw "PipelinePlan validation failed: UNKNOWN route plans must be resolved before executor dry-run."
    }

    Assert-PipelinePlanProperties -Value $Plan.output -Path '$.output' -Required @(
        'path','container','extension','remuxRequired','copyUnchangedPossible'
    ) -Allowed @('path','container','extension','sourceContainer','remuxRequired','copyUnchangedPossible')

    $validOperations = @(
        'copy_source','copy_video','encode_video','copy_audio','transcode_audio','drop_audio',
        'copy_subtitle','convert_subtitle','burn_subtitle','drop_subtitle','mux_container',
        'verify_output','publish_safety','no_command'
    )
    $validStreamTypes = @('source','video','audio','subtitle','container','verification','publish')

    $streamActions = @(Get-PipelinePlanArray -Value $Plan.streamActions)
    if ($streamActions.Count -eq 0) {
        throw 'PipelinePlan validation failed: streamActions must not be empty.'
    }
    foreach ($action in $streamActions) {
        Assert-PipelinePlanProperties -Value $action -Path '$.streamActions[]' -Required @(
            'streamType','action'
        ) -Allowed @('streamType','streamIndex','action','inputCodec','outputCodec','reasonCodes')
        $streamType = [string]$action.streamType
        Assert-PipelinePlanEnum -Value $streamType -Path '$.streamActions[].streamType' -Allowed @('video','audio','subtitle','container')
        switch ($streamType) {
            'video'     { Assert-PipelinePlanEnum -Value ([string]$action.action) -Path '$.streamActions[video].action' -Allowed @('copy','encode','reject','unknown') }
            'audio'     { Assert-PipelinePlanEnum -Value ([string]$action.action) -Path '$.streamActions[audio].action' -Allowed @('copy','transcode','drop','unknown') }
            'subtitle'  { Assert-PipelinePlanEnum -Value ([string]$action.action) -Path '$.streamActions[subtitle].action' -Allowed @('copy','convert','burn','drop','unknown') }
            'container' { Assert-PipelinePlanEnum -Value ([string]$action.action) -Path '$.streamActions[container].action' -Allowed @('keep','remux','change','unknown') }
        }
    }

    $videoAction = Get-PipelinePlanSingleStreamAction -Plan $Plan -StreamType 'video'
    $containerAction = Get-PipelinePlanSingleStreamAction -Plan $Plan -StreamType 'container'

    if ([string]$Plan.routeSummary -in @('COPY','REMUX') -and [string]$videoAction.action -ne 'copy') {
        throw "PipelinePlan validation failed: $($Plan.routeSummary) route cannot encode video."
    }
    if ([string]$Plan.routeSummary -eq 'ENCODE' -and [string]$videoAction.action -ne 'encode') {
        throw 'PipelinePlan validation failed: ENCODE route must carry video action encode.'
    }
    if ([string]$Plan.routeSummary -eq 'COPY' -and [string]$containerAction.action -ne 'keep') {
        throw 'PipelinePlan validation failed: COPY route must keep the container.'
    }

    foreach ($subtitle in @(Get-PipelinePlanStreamActions -Plan $Plan -StreamType 'subtitle')) {
        if ([string]$subtitle.action -eq 'burn' -and [string]$videoAction.action -ne 'encode') {
            throw 'PipelinePlan validation failed: subtitle burn requires video action encode.'
        }
    }

    foreach ($reason in @(Get-PipelinePlanArray -Value $Plan.reasonSummary)) {
        Assert-PipelinePlanProperties -Value $reason -Path '$.reasonSummary[]' -Required @('code','text') -Allowed @('code','text','enforcement','legacyCode')
    }

    foreach ($fallback in @(Get-PipelinePlanArray -Value $Plan.runtimeFallbacks)) {
        Assert-PipelinePlanProperties -Value $fallback -Path '$.runtimeFallbacks[]' -Required @(
            'fallbackId','mode','trigger','action'
        ) -Allowed @('fallbackId','mode','trigger','action','owner','reasonCodes','notes')
        Assert-PipelinePlanEnum -Value ([string]$fallback.mode) -Path '$.runtimeFallbacks[].mode' -Allowed @('conditional_branch','typed_executor_outcome')
    }

    $commandPlans = @(Get-PipelinePlanArray -Value $Plan.commandPlans)
    if ($commandPlans.Count -eq 0) {
        throw 'PipelinePlan validation failed: commandPlans must not be empty.'
    }
    foreach ($commandPlan in $commandPlans) {
        Assert-PipelinePlanProperties -Value $commandPlan -Path '$.commandPlans[]' -Required @(
            'commandPlanId','routeSummary','dryRunOnly','canExecute','previewKind','steps'
        ) -Allowed @(
            'commandPlanId','routeSummary','dryRunOnly','canExecute','previewKind','executor',
            'reasonCodes','previewLines','steps','warnings'
        )
        if (-not [bool]$commandPlan.dryRunOnly) {
            throw 'PipelinePlan validation failed: commandPlans[].dryRunOnly must be true in Phase 07B.'
        }
        if ([bool]$commandPlan.canExecute) {
            throw 'PipelinePlan validation failed: commandPlans[].canExecute must remain false in Phase 07B.'
        }
        if ([string]$commandPlan.previewKind -ne 'abstract') {
            throw "PipelinePlan validation failed: commandPlans[].previewKind must be 'abstract'."
        }
        foreach ($step in @(Get-PipelinePlanArray -Value $commandPlan.steps)) {
            Assert-PipelinePlanProperties -Value $step -Path '$.commandPlans[].steps[]' -Required @(
                'stepId','operation','streamType','label','dryRunText'
            ) -Allowed @('stepId','operation','streamType','streamIndex','label','dryRunText','details')
            Assert-PipelinePlanEnum -Value ([string]$step.operation) -Path '$.commandPlans[].steps[].operation' -Allowed $validOperations
            Assert-PipelinePlanEnum -Value ([string]$step.streamType) -Path '$.commandPlans[].steps[].streamType' -Allowed $validStreamTypes
            if ([string]$Plan.routeSummary -in @('COPY','REMUX') -and [string]$step.operation -eq 'encode_video') {
                throw "PipelinePlan validation failed: $($Plan.routeSummary) plan contains encode_video step."
            }
        }
    }

    return $true
}

function ConvertFrom-PipelinePlanJson {
    param([Parameter(Mandatory)] [string] $Json)

    try {
        $plan = $Json | ConvertFrom-Json -Depth 100
    } catch {
        throw "PipelinePlan JSON parse failed: $($_.Exception.Message)"
    }
    Assert-PipelinePlanValid -Plan $plan | Out-Null
    return $plan
}

function Read-PipelinePlanJson {
    param([Parameter(Mandatory)] [string] $Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "PipelinePlan JSON path does not exist: $Path"
    }
    return ConvertFrom-PipelinePlanJson -Json (Get-Content -Raw -LiteralPath $Path)
}
