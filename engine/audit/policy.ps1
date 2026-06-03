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

function Get-DefaultAuditScorePolicy {
    return @{
        redownload_bucket = 100
        high_issue        = 90
        rerun_bucket      = 60
        medium_issue      = 40
        review_bucket     = 20
        fallback_issue    = 10
        redownload_bonus  = 100
        rerun_bonus       = 40
    }
}

function ConvertTo-AuditScorePolicy {
    param([object]$Policy)

    $defaults = Get-DefaultAuditScorePolicy
    $normalized = @{}
    foreach ($key in $defaults.Keys) {
        $value = $defaults[$key]
        try {
            $candidate = $null
            if ($Policy -is [hashtable] -and $Policy.ContainsKey($key)) {
                $candidate = $Policy[$key]
            } elseif ($null -ne $Policy -and $Policy.PSObject.Properties.Name -contains $key) {
                $candidate = $Policy.$key
            }
            if ($null -ne $candidate) {
                $value = [int]$candidate
            }
        } catch {
            $value = $defaults[$key]
        }
        if ($value -lt 0) { $value = 0 }
        if ($value -gt 1000) { $value = 1000 }
        $normalized[$key] = $value
    }
    return $normalized
}

function Import-AuditScorePolicy {
    param([string]$Path)

    $defaults = ConvertTo-AuditScorePolicy -Policy $null
    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) {
        return $defaults
    }
    try {
        $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($null -ne $raw -and $raw.PSObject.Properties.Name -contains 'policy') {
            return ConvertTo-AuditScorePolicy -Policy $raw.policy
        }
        return ConvertTo-AuditScorePolicy -Policy $raw
    } catch {
        return $defaults
    }
}

function Get-AuditScorePolicyValue {
    param(
        [string]$Key,
        [int]$Default
    )

    if ($null -eq $script:AuditScorePolicy) { return $Default }
    if ($script:AuditScorePolicy.ContainsKey($Key)) {
        return [int]$script:AuditScorePolicy[$Key]
    }
    return $Default
}

function ConvertTo-AuditIgnoreKey {
    param([object]$Path)

    if ($null -eq $Path) { return '' }
    return ([string]$Path).Trim().Replace('\', '/').TrimEnd('/').ToLowerInvariant()
}

function Import-AuditIgnoreManifest {
    param([string]$Path)

    $entries = @{}
    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) {
        return $entries
    }
    try {
        $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($null -eq $raw -or -not ($raw.PSObject.Properties.Name -contains 'entries')) {
            return $entries
        }
        foreach ($property in $raw.entries.PSObject.Properties) {
            $key = ConvertTo-AuditIgnoreKey -Path $property.Name
            if ($key) { $entries[$key] = $property.Value }
        }
    } catch {}
    return $entries
}

function Get-AuditIgnoreEntry {
    param([object]$Path)

    if ($null -eq $script:AuditIgnoreEntries) { return $null }
    $key = ConvertTo-AuditIgnoreKey -Path $Path
    if ($key -and $script:AuditIgnoreEntries.ContainsKey($key)) {
        return $script:AuditIgnoreEntries[$key]
    }
    return $null
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
    if ($Issue.Bucket -eq 'REDOWNLOAD_CANDIDATE') { return Get-AuditScorePolicyValue -Key 'redownload_bucket' -Default 100 }
    if ($Issue.Code -in $script:HighPriorityIssueCodes) { return Get-AuditScorePolicyValue -Key 'high_issue' -Default 90 }
    if ($Issue.Bucket -eq 'RERUN_PIPELINE') { return Get-AuditScorePolicyValue -Key 'rerun_bucket' -Default 60 }
    if ($Issue.Code -in $script:MediumPriorityIssueCodes) { return Get-AuditScorePolicyValue -Key 'medium_issue' -Default 40 }
    if ($Issue.Bucket -eq 'REVIEW') { return Get-AuditScorePolicyValue -Key 'review_bucket' -Default 20 }
    return Get-AuditScorePolicyValue -Key 'fallback_issue' -Default 10
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
        $score += Get-AuditScorePolicyValue -Key 'redownload_bonus' -Default 100
    } elseif (@($effective | Where-Object { $_.Bucket -eq 'RERUN_PIPELINE' }).Count -gt 0) {
        $score += Get-AuditScorePolicyValue -Key 'rerun_bonus' -Default 40
    }

    return $score
}

