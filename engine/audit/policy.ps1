# Audit issue prioritization and bucket policy helpers.

function Convert-ToLowerInvariantSafe {
    param([object]$Value)

    if ($null -eq $Value) { return '' }
    return ([string]$Value).ToLowerInvariant()
}

function Get-BucketRank {
    param([string]$Bucket)

    switch ($Bucket) {
        'REDOWNLOAD_CANDIDATE' { return 3 }
        'RERUN_PIPELINE'       { return 2 }
        'REVIEW'               { return 1 }
        default                { return 0 }
    }
}

function Get-PriorityLevelRank {
    param([string]$PriorityLevel)

    switch ($PriorityLevel) {
        'HIGH'   { return 3 }
        'MEDIUM' { return 2 }
        'LOW'    { return 1 }
        default  { return 0 }
    }
}

function Get-NonSidecarIssues {
    param([array]$Issues)

    return @($Issues | Where-Object { $_.Code -notin $script:SidecarIssueCodes })
}

function Get-EffectiveIssues {
    param([array]$Issues)

    $nonSidecar = @(Get-NonSidecarIssues -Issues $Issues)
    if ($nonSidecar.Count -gt 0) { return $nonSidecar }
    return @($Issues)
}

function Get-IssueEffectiveBucket {
    param([array]$Issues)

    $effective = @(Get-EffectiveIssues -Issues $Issues)
    if ($effective.Count -eq 0) { return 'OK' }

    $topIssue = $effective |
        Sort-Object @{ Expression = { Get-BucketRank $_.Bucket }; Descending = $true }, Code |
        Select-Object -First 1

    if ($topIssue) { return $topIssue.Bucket }
    return 'OK'
}

function Get-PrimaryIssue {
    param([array]$Issues)

    $effective = @(Get-EffectiveIssues -Issues $Issues)
    if ($effective.Count -eq 0) { return $null }

    return @(
        $effective |
            Sort-Object `
                @{ Expression = {
                    if ($_.Code -in $script:HighPriorityIssueCodes) { 2 }
                    elseif ($_.Code -in $script:MediumPriorityIssueCodes) { 1 }
                    else { 0 }
                }; Descending = $true }, `
                @{ Expression = { Get-BucketRank $_.Bucket }; Descending = $true }, `
                Code
    )[0]
}

function Get-PriorityFixLevel {
    param([array]$Issues)

    $effective = @(Get-EffectiveIssues -Issues $Issues)
    if ($effective.Count -eq 0) { return 'NONE' }

    if (@($effective | Where-Object { $_.Bucket -eq 'REDOWNLOAD_CANDIDATE' -or $_.Code -in $script:HighPriorityIssueCodes }).Count -gt 0) {
        return 'HIGH'
    }
    if (@($effective | Where-Object { $_.Bucket -eq 'RERUN_PIPELINE' -or $_.Code -in $script:MediumPriorityIssueCodes }).Count -gt 0) {
        return 'MEDIUM'
    }
    return 'LOW'
}

function Get-IssuePriorityWeight {
    param($Issue)

    if ($null -eq $Issue) { return 0 }
    if ($Issue.Bucket -eq 'REDOWNLOAD_CANDIDATE') { return 100 }
    if ($Issue.Code -in $script:HighPriorityIssueCodes) { return 90 }
    if ($Issue.Bucket -eq 'RERUN_PIPELINE') { return 60 }
    if ($Issue.Code -in $script:MediumPriorityIssueCodes) { return 40 }
    if ($Issue.Bucket -eq 'REVIEW') { return 20 }
    return 10
}

function Get-PriorityScore {
    param([array]$Issues)

    $effective = @(Get-EffectiveIssues -Issues $Issues)
    if ($effective.Count -eq 0) { return 0 }

    $score = 0
    foreach ($issue in $effective) {
        $score += Get-IssuePriorityWeight -Issue $issue
    }

    if (@($effective | Where-Object { $_.Bucket -eq 'REDOWNLOAD_CANDIDATE' }).Count -gt 0) {
        $score += 100
    } elseif (@($effective | Where-Object { $_.Bucket -eq 'RERUN_PIPELINE' }).Count -gt 0) {
        $score += 40
    }

    return $score
}

