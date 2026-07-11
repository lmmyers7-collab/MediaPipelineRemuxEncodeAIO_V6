# Extracted from ops/scripts/release/test.ps1. Responsibility: rename-filter deployment and retention policy checks

function Get-ReleaseSortedMapKeys {
    param($Map)

    if ($null -eq $Map) { return @() }
    try {
        return @($Map.Keys | ForEach-Object { [string]$_ } | Sort-Object)
    } catch {
        return @()
    }
}

function Get-ReleaseRenameFilterDeploymentBaseline {
    param(
        [Parameter(Mandatory = $true)][string]$ConfigPath,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        Write-Fail "$Label missing from release package: $ConfigPath"
        $script:Failed = $true
        return $null
    }

    try {
        $config = Import-PowerShellDataFile -Path $ConfigPath
    } catch {
        Write-Fail "$Label could not be parsed as a PowerShell data file: $($_.Exception.Message)"
        $script:Failed = $true
        return $null
    }

    $ok = $true
    foreach ($key in @('RenameMovieFilterOptions', 'RenameMovieFilterTerms', 'RenameMovieRemoveTerms')) {
        if (-not (Test-ReleaseMapContainsKey -Map $config -Key $key)) {
            Write-Fail "$Label must include packaged custom rename filter key '$key'."
            $script:Failed = $true
            $ok = $false
        }
    }
    if (-not $ok) { return $null }

    $options = $config['RenameMovieFilterOptions']
    $terms = $config['RenameMovieFilterTerms']
    $categories = @(Get-ReleaseSortedMapKeys -Map $options)
    if ($categories.Count -eq 0) {
        Write-Fail "$Label RenameMovieFilterOptions must include at least one packaged custom category."
        $script:Failed = $true
        $ok = $false
    }

    $termCategories = @(Get-ReleaseSortedMapKeys -Map $terms)
    if (-not (Test-ReleaseStringArrayEquals -Actual $termCategories -Expected $categories -Label "$Label RenameMovieFilterTerms categories")) {
        $ok = $false
    }

    foreach ($category in $categories) {
        if ($options[$category] -isnot [bool]) {
            Write-Fail "$Label RenameMovieFilterOptions.$category must be a boolean."
            $script:Failed = $true
            $ok = $false
        }
        if (-not (Test-ReleaseMapContainsKey -Map $terms -Key $category)) {
            Write-Fail "$Label RenameMovieFilterTerms missing category '$category'."
            $script:Failed = $true
            $ok = $false
        } elseif (@(ConvertTo-ReleaseStringArray -Value $terms[$category]).Count -eq 0) {
            Write-Fail "$Label RenameMovieFilterTerms.$category must keep the packaged custom term list."
            $script:Failed = $true
            $ok = $false
        }
    }
    if (-not $ok) { return $null }

    return [pscustomobject]@{
        Categories = $categories
        Options = $options
        Terms = $terms
        RemoveTerms = @(ConvertTo-ReleaseStringArray -Value $config['RenameMovieRemoveTerms'])
    }
}

function Test-ReleaseRenameFilterConfigMatchesExpected {
    param(
        [Parameter(Mandatory = $true)][string]$ConfigPath,
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)]$ExpectedOptions,
        [Parameter(Mandatory = $true)]$ExpectedTerms,
        [Parameter(Mandatory = $true)]$ExpectedRemoveTerms,
        [Parameter(Mandatory = $true)][string[]]$ExpectedCategories
    )

    $ok = $true
    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        Write-Fail "$Label missing from release package: $ConfigPath"
        $script:Failed = $true
        return $false
    }

    try {
        $config = Import-PowerShellDataFile -Path $ConfigPath
    } catch {
        Write-Fail "$Label could not be parsed as a PowerShell data file: $($_.Exception.Message)"
        $script:Failed = $true
        return $false
    }

    foreach ($key in @('RenameMovieFilterOptions', 'RenameMovieFilterTerms', 'RenameMovieRemoveTerms')) {
        if (-not (Test-ReleaseMapContainsKey -Map $config -Key $key)) {
            Write-Fail "$Label must include packaged custom rename filter key '$key'."
            $script:Failed = $true
            $ok = $false
        }
    }
    if (-not $ok) { return $false }

    $options = $config['RenameMovieFilterOptions']
    $terms = $config['RenameMovieFilterTerms']
    $actualOptionCategories = @(Get-ReleaseSortedMapKeys -Map $options)
    $actualTermCategories = @(Get-ReleaseSortedMapKeys -Map $terms)
    if (-not (Test-ReleaseStringArrayEquals -Actual $actualOptionCategories -Expected $ExpectedCategories -Label "$Label RenameMovieFilterOptions categories")) {
        $ok = $false
    }
    if (-not (Test-ReleaseStringArrayEquals -Actual $actualTermCategories -Expected $ExpectedCategories -Label "$Label RenameMovieFilterTerms categories")) {
        $ok = $false
    }

    foreach ($category in $ExpectedCategories) {
        if (-not (Test-ReleaseMapContainsKey -Map $options -Key $category)) {
            Write-Fail "$Label RenameMovieFilterOptions missing category '$category'."
            $script:Failed = $true
            $ok = $false
        } else {
            $actualOption = $options[$category]
            $expectedOption = $ExpectedOptions[$category]
            if ($actualOption -isnot [bool]) {
                Write-Fail "$Label RenameMovieFilterOptions.$category must be a boolean."
                $script:Failed = $true
                $ok = $false
            } elseif ([bool]$actualOption -ne [bool]$expectedOption) {
                Write-Fail "$Label RenameMovieFilterOptions.$category drifted. Actual='$actualOption' Expected='$expectedOption'"
                $script:Failed = $true
                $ok = $false
            }
        }

        if (-not (Test-ReleaseMapContainsKey -Map $terms -Key $category)) {
            Write-Fail "$Label RenameMovieFilterTerms missing category '$category'."
            $script:Failed = $true
            $ok = $false
        } elseif (-not (Test-ReleaseStringArrayEquals -Actual $terms[$category] -Expected $ExpectedTerms[$category] -Label "$Label RenameMovieFilterTerms.$category")) {
            $ok = $false
        }
    }

    if (-not (Test-ReleaseStringArrayEquals -Actual $config['RenameMovieRemoveTerms'] -Expected $ExpectedRemoveTerms -Label "$Label RenameMovieRemoveTerms")) {
        $ok = $false
    }

    if ($ok) {
        Write-Ok "$Label keeps packaged custom rename filters."
    }
    return $ok
}

function Test-ReleaseCustomRenameFilterRetention {
    Write-Section 'Custom Rename Filters'

    $templatePath = Join-Path $script:BundleRoot 'ops\pipeline\config\MediaPipeline_config_template.psd1'
    $baseline = Get-ReleaseRenameFilterDeploymentBaseline -ConfigPath $templatePath -Label 'Config template'
    if ($null -eq $baseline) { return }

    $allOk = $true
    foreach ($configFile in @(
        @{ Label = 'Config template'; Path = $templatePath },
        @{ Label = 'Default config profile'; Path = (Join-Path $script:BundleRoot 'ops\pipeline\config\profiles\Default.psd1') }
    )) {
        if (-not (Test-ReleaseRenameFilterConfigMatchesExpected `
            -ConfigPath $configFile.Path `
            -Label $configFile.Label `
            -ExpectedOptions $baseline.Options `
            -ExpectedTerms $baseline.Terms `
            -ExpectedRemoveTerms $baseline.RemoveTerms `
            -ExpectedCategories $baseline.Categories)) {
            $allOk = $false
        }
    }

    if ($allOk) {
        Write-Ok 'Custom rename filter deployment baseline retained.'
    }
}
