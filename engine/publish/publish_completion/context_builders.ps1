# Low-risk publish completion builders. These functions do not move, copy,
# reveal, delete, or write media artifacts.

function Get-PublishCopyFailureClassification {
    param(
        $CopyResult
    )

    if ($null -eq $CopyResult) {
        return [pscustomobject]@{
            IsOutputSpace        = $false
            IsOutputSpaceUnknown = $false
            Reason               = ''
            ReasonCode           = ''
        }
    }

    $reasonCode = ''
    if ($CopyResult.PSObject.Properties['ReasonCode']) {
        $reasonCode = [string]$CopyResult.ReasonCode
    }

    $reason = ''
    if ($CopyResult.PSObject.Properties['Reason']) {
        $reason = [string]$CopyResult.Reason
    }

    $isOutputSpaceUnknown = ($reasonCode -eq 'OUTPUT_DESTINATION_SPACE_UNKNOWN')
    $isOutputSpace = ($reasonCode -in @('OUTPUT_DESTINATION_LOW_SPACE', 'OUTPUT_DESTINATION_SPACE_UNKNOWN'))
    if (-not $isOutputSpace) {
        $isOutputSpace = ($reason -match 'insufficient free space|not enough space|disk full|No space left on device')
    }

    return [pscustomobject]@{
        IsOutputSpace        = [bool]$isOutputSpace
        IsOutputSpaceUnknown = [bool]$isOutputSpaceUnknown
        Reason               = $reason
        ReasonCode           = $reasonCode
    }
}

function Test-PublishCopyFailureIsOutputSpace {
    $classification = Get-PublishCopyFailureClassification -CopyResult $script:LastCopyFileRobocopyResult
    return [bool]$classification.IsOutputSpace
}

function Test-PublishCopyFailureIsOutputSpaceUnknown {
    $classification = Get-PublishCopyFailureClassification -CopyResult $script:LastCopyFileRobocopyResult
    return [bool]$classification.IsOutputSpaceUnknown
}

function Get-PublishCopyFailureReason {
    $classification = Get-PublishCopyFailureClassification -CopyResult $script:LastCopyFileRobocopyResult
    return [string]$classification.Reason
}

function New-PublishEvidenceContext {
    param(
        [Parameter(Mandatory)] $SourceFile,
        [Parameter(Mandatory)] $Paths,
        [Parameter(Mandatory)] [string] $StagePrefix,
        [string] $RouteReasonCode = '',
        [string] $RouteReason = ''
    )

    $sourceIdentity = Get-SourceIdentityKey $SourceFile
    $sourceIdentityV2 = Get-SourceIdentityKeyV2 $SourceFile
    $sourceMTimeUtc = $SourceFile.LastWriteTimeUtc.ToString('o')
    $publishTransactionId = New-PublishTransactionId
    $stageName = $StagePrefix.ToLowerInvariant()
    $logPrefix = $StagePrefix.ToUpperInvariant()

    $effectiveRouteReasonCode = $RouteReasonCode
    if ([string]::IsNullOrWhiteSpace($effectiveRouteReasonCode) -and $script:CurrentRouteReasonCode) {
        $effectiveRouteReasonCode = [string]$script:CurrentRouteReasonCode
    }

    $effectiveRouteReason = $RouteReason
    if ([string]::IsNullOrWhiteSpace($effectiveRouteReason) -and $script:CurrentRouteReason) {
        $effectiveRouteReason = [string]$script:CurrentRouteReason
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

    $mediaType = ''
    $plexPlan = $null
    if ($Paths -is [System.Collections.IDictionary] -and $Paths.Contains('PlexPlan')) {
        $plexPlan = $Paths['PlexPlan']
    } elseif ($Paths -and $Paths.PSObject.Properties['PlexPlan']) {
        $plexPlan = $Paths.PlexPlan
    }
    if ($plexPlan) {
        $planMediaKind = [string]$plexPlan.MediaKind
        if (-not [string]::IsNullOrWhiteSpace($planMediaKind)) {
            $mediaType = $planMediaKind.Trim().ToLowerInvariant()
        }
    }

    $libraryProfileEvidence = if (Get-Command -Name Get-MediaPipelineLibraryProfileEvidenceForPath -ErrorAction SilentlyContinue) {
        Get-MediaPipelineLibraryProfileEvidenceForPath -SourcePath $SourceFile.FullName
    } else {
        $null
    }

    return [pscustomobject]@{
        SourceIdentity         = $sourceIdentity
        SourceIdentityV2       = $sourceIdentityV2
        SourceMTimeUtc         = $sourceMTimeUtc
        PublishTransactionId   = $publishTransactionId
        StageName              = $stageName
        LogPrefix              = $logPrefix
        RouteReasonCode        = $effectiveRouteReasonCode
        RouteReason            = $effectiveRouteReason
        FolderPolicyMetadata   = $folderPolicyMetadata
        RoutePlanMetadata      = $routePlanMetadata
        MediaType              = $mediaType
        LibraryProfileEvidence = $libraryProfileEvidence
    }
}

function New-PendingParkArguments {
    param(
        [Parameter(Mandatory)] $EvidenceContext,
        [Parameter(Mandatory)] $SourceFile,
        [Parameter(Mandatory)] $Paths,
        [Parameter(Mandatory)] [string] $Route,
        [Parameter(Mandatory)] [string] $PublishMode,
        [System.Collections.IDictionary] $Extra = $null
    )

    $parkArgs = @{
        LocalOut = $Paths.LocalOut; ServerOut = $Paths.ServerOut; Route = $Route
        MediaType = $EvidenceContext.MediaType
        RouteReasonCode = $EvidenceContext.RouteReasonCode; RouteReason = $EvidenceContext.RouteReason
        SourceIdentity = $EvidenceContext.SourceIdentity; SourceIdentityV2 = $EvidenceContext.SourceIdentityV2
        SourcePath = $SourceFile.FullName; SourceSize = $SourceFile.Length; SourceMTimeUtc = $EvidenceContext.SourceMTimeUtc
        PublishTransactionId = $EvidenceContext.PublishTransactionId; PublishMode = $PublishMode
        FolderPolicyMetadata = $EvidenceContext.FolderPolicyMetadata
        RoutePlanMetadata = $EvidenceContext.RoutePlanMetadata
    }

    if ($Extra) {
        foreach ($key in $Extra.Keys) {
            $parkArgs[$key] = $Extra[$key]
        }
    }

    return $parkArgs
}
