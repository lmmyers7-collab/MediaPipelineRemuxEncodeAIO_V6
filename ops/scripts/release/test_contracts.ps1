# Extracted from ops/scripts/release/test.ps1. Responsibility: static assets, launcher, manifest, privacy, and version contracts

function Test-WebStaticAssetReferences {
    param([Parameter(Mandatory = $true)][string]$StaticRoot)

    Write-Section 'Web Static Asset References'

    $indexPath = Join-Path $StaticRoot 'index.html'
    $assetsRoot = Join-Path $StaticRoot 'assets'
    if (-not (Test-Path -LiteralPath $indexPath -PathType Leaf)) {
        Write-Fail "Web static index missing: $indexPath"
        $script:Failed = $true
        return
    }
    if (-not (Test-Path -LiteralPath $assetsRoot -PathType Container)) {
        Write-Fail "Web static assets directory missing: $assetsRoot"
        $script:Failed = $true
        return
    }

    try {
        $html = Get-Content -LiteralPath $indexPath -Raw
    } catch {
        Write-Fail "Web static index could not be read: $($_.Exception.Message)"
        $script:Failed = $true
        return
    }

    if ($html -match '__MEDIA_PIPELINE_BOOTSTRAP__') {
        Write-Ok 'Web static index bootstrap placeholder is present.'
    } else {
        Write-Fail 'Web static index is missing the backend bootstrap placeholder.'
        $script:Failed = $true
    }

    $includeMatches = [regex]::Matches($html, '<!--\s*mp-include:\s*([^>]+?)\s*-->')
    $includeNames = [System.Collections.Generic.SortedSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($match in $includeMatches) {
        $includeName = $match.Groups[1].Value.Trim()
        if ([string]::IsNullOrWhiteSpace($includeName) -or $includeName -notmatch '^partials/[A-Za-z0-9_.-]+\.html$' -or $includeName -match '(^|/)\.\.(/|$)' -or $includeName -match '^[\\/]' -or $includeName -match ':') {
            Write-Fail "Unsafe Web static include reference: $includeName"
            $script:Failed = $true
            continue
        }
        [void]$includeNames.Add($includeName)
    }

    $missingIncludes = @()
    foreach ($includeName in $includeNames) {
        $relativeInclude = $includeName -replace '/', '\'
        $includePath = Join-Path $StaticRoot $relativeInclude
        if (-not (Test-Path -LiteralPath $includePath -PathType Leaf)) {
            $missingIncludes += $includeName
        }
    }

    if ($missingIncludes.Count -gt 0) {
        Write-Fail 'Web static index references missing include partials:'
        $missingIncludes | ForEach-Object { Write-Host "  $_" }
        $script:Failed = $true
        return
    }

    if ($includeNames.Count -gt 0) {
        Write-Ok ("Web static index references {0} include partial(s); all are present." -f $includeNames.Count)
    }

    $matches = [regex]::Matches($html, '(?:src|href)="/assets/([^"#?]+)(?:[?#][^"]*)?"')
    if ($matches.Count -eq 0) {
        Write-Fail 'Web static index does not reference any /assets/ files.'
        $script:Failed = $true
        return
    }

    $assetNames = [System.Collections.Generic.SortedSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($match in $matches) {
        $assetName = [System.Uri]::UnescapeDataString($match.Groups[1].Value)
        if ([string]::IsNullOrWhiteSpace($assetName) -or $assetName -match '(^|/)\.\.(/|$)' -or $assetName -match '^[\\/]' -or $assetName -match ':') {
            Write-Fail "Unsafe Web static asset reference: /assets/$assetName"
            $script:Failed = $true
            continue
        }
        [void]$assetNames.Add($assetName)
    }

    $missing = @()
    foreach ($assetName in $assetNames) {
        $relativeAsset = $assetName -replace '/', '\'
        $assetPath = Join-Path $assetsRoot $relativeAsset
        if (-not (Test-Path -LiteralPath $assetPath -PathType Leaf)) {
            $missing += "/assets/$assetName"
        }
    }

    if ($missing.Count -gt 0) {
        Write-Fail 'Web static index references missing assets:'
        $missing | ForEach-Object { Write-Host "  $_" }
        $script:Failed = $true
        return
    }

    Write-Ok ("Web static index references {0} asset file(s); all are present." -f $assetNames.Count)
}

function Test-ApiBrowserLauncherTokenPolicy {
    Write-Section 'API Browser Launcher Token Policy'

    $launcherPath = Join-Path $script:BundleRoot 'apps\desktop\launchers\Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1'
    if (-not (Test-Path -LiteralPath $launcherPath -PathType Leaf)) {
        Write-Fail "API browser launcher missing: $launcherPath"
        $script:Failed = $true
        return
    }

    try {
        $text = Get-Content -LiteralPath $launcherPath -Raw
    } catch {
        Write-Fail "API browser launcher could not be read: $($_.Exception.Message)"
        $script:Failed = $true
        return
    }

    $requiredPatterns = @(
        @{ Pattern = '\[switch\]\$NoTokenDevMode'; Label = 'dev-only NoTokenDevMode switch' },
        @{ Pattern = 'Token auth: enabled \(browser receives a same-origin HttpOnly auth cookie\)'; Label = 'default token-enabled operator banner' },
        @{ Pattern = 'Token auth: DISABLED by explicit -NoTokenDevMode'; Label = 'explicit no-token warning banner' },
        @{ Pattern = 'if \(\$NoTokenDevMode\)[\s\S]+?\$apiArgs \+= ''--no-token'''; Label = 'no-token argument gated by NoTokenDevMode' },
        @{ Pattern = 'MEDIAPIPELINE_ALLOW_NO_TOKEN_DEV'; Label = 'explicit backend no-token environment gate' }
    )
    foreach ($entry in $requiredPatterns) {
        if ($text -match $entry.Pattern) {
            Write-Ok "API browser launcher includes $($entry.Label)."
        } else {
            Write-Fail "API browser launcher is missing $($entry.Label)."
            $script:Failed = $true
        }
    }

    $defaultArgsMatch = [regex]::Match($text, '\$apiArgs\s*=\s*@\((?<body>[\s\S]*?)\)\s*if \(\$NoTokenDevMode\)')
    if (-not $defaultArgsMatch.Success) {
        Write-Fail 'API browser launcher default argument block could not be identified.'
        $script:Failed = $true
    } elseif ($defaultArgsMatch.Groups['body'].Value -match '--no-token') {
        Write-Fail 'API browser launcher default arguments must not disable token auth.'
        $script:Failed = $true
    } else {
        Write-Ok 'API browser launcher keeps token auth enabled by default.'
    }
}

function Test-ReleaseManifestHygiene {
    param([Parameter(Mandatory = $true)][string]$ManifestPath)

    Write-Section 'Release Manifest'
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        Record-ReleaseGateSkip 'release_manifest.json not found. Manifest hygiene checks are skipped for source/dev folders.'
        return
    }

    try {
        $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json -ErrorAction Stop
    } catch {
        Write-Fail "release_manifest.json could not be parsed: $($_.Exception.Message)"
        $script:Failed = $true
        return
    }

    $schemaVersion = [string](Get-ObjectPropertyValue -Object $manifest -Name 'schema_version' -Default '')
    if ($schemaVersion -eq 'mediapipeline_release_manifest.v1') {
        Write-Ok "Manifest schema: $schemaVersion"
    } else {
        Write-Fail "Unexpected release manifest schema: $schemaVersion"
        $script:Failed = $true
    }

    $summary = Get-ObjectPropertyValue -Object $manifest -Name 'summary'
    $personalConfigIncluded = ConvertTo-ReleaseBool -Value (Get-ObjectPropertyValue -Object $summary -Name 'personal_config_included') -Default $false
    $devDocsIncluded = ConvertTo-ReleaseBool -Value (Get-ObjectPropertyValue -Object $summary -Name 'dev_docs_included') -Default $false
    $optionalToolsIncluded = ConvertTo-ReleaseBool -Value (Get-ObjectPropertyValue -Object $summary -Name 'optional_tools_included') -Default $false
    $toolDocsIncluded = ConvertTo-ReleaseBool -Value (Get-ObjectPropertyValue -Object $summary -Name 'tool_docs_included') -Default $false
    $tauriPreviewBinaryIncluded = ConvertTo-ReleaseBool -Value (Get-ObjectPropertyValue -Object $summary -Name 'tauri_preview_binary_included') -Default $false

    $releasePolicy = Get-ObjectPropertyValue -Object $manifest -Name 'release_policy'
    $releasePolicySchema = [string](Get-ObjectPropertyValue -Object $releasePolicy -Name 'schema_version' -Default '')
    if ($releasePolicySchema -eq 'mediapipeline_release_policy.v1') {
        Write-Ok "Release policy schema: $releasePolicySchema"
    } else {
        Write-Fail "Unexpected release policy schema: $releasePolicySchema"
        $script:Failed = $true
    }

    if ($devDocsIncluded) {
        Write-Warn 'Manifest says development docs were intentionally included. Docs housekeeping quarantine absence check skipped.'
    }
    if ($personalConfigIncluded) {
        Write-Warn 'Manifest says personal config was intentionally included. Live config absence check skipped.'
    }
    if ($optionalToolsIncluded) {
        Write-Warn 'Manifest says optional tool binaries were intentionally included. Optional tool absence checks skipped.'
    }
    if ($toolDocsIncluded) {
        Write-Warn 'Manifest says bundled tool docs/examples were intentionally included. Tool doc absence checks skipped.'
    }

    if (-not (. Import-MediaPipelineReleasePolicy)) { return }

    $rules = @(
        Get-MediaPipelineReleaseHygieneRules `
            -PersonalConfigIncluded:$personalConfigIncluded `
            -DevDocsIncluded:$devDocsIncluded `
            -OptionalToolsIncluded:$optionalToolsIncluded `
            -ToolDocsIncluded:$toolDocsIncluded `
            -TauriPreviewBinaryIncluded:$tauriPreviewBinaryIncluded
    )

    foreach ($rule in $rules) {
        $kind = [string](Get-ObjectPropertyValue -Object $rule -Name 'kind' -Default '')
        $label = [string](Get-ObjectPropertyValue -Object $rule -Name 'label' -Default 'release hygiene rule')
        switch ($kind) {
            'path_absent' {
                Assert-ReleasePathAbsent -RelativePath ([string](Get-ObjectPropertyValue -Object $rule -Name 'relative_path' -Default '')) -Label $label
            }
            'pattern_absent' {
                Assert-ReleasePatternAbsent -RelativePattern ([string](Get-ObjectPropertyValue -Object $rule -Name 'relative_pattern' -Default '')) -Label $label
            }
            'path_present' {
                Assert-ReleasePathPresent -RelativePath ([string](Get-ObjectPropertyValue -Object $rule -Name 'relative_path' -Default '')) -Label $label
            }
            default {
                Write-Fail "Unknown release hygiene rule kind: $kind"
                $script:Failed = $true
            }
        }
    }

    # The copied file list intentionally excludes this manifest itself.
    $integrity = Get-ObjectPropertyValue -Object $manifest -Name 'integrity'
    $integrityFiles = @((Get-ObjectPropertyValue -Object $integrity -Name 'files' -Default @()))
    if ([string](Get-ObjectPropertyValue -Object $integrity -Name 'algorithm' -Default '') -ne 'sha256' -or $integrityFiles.Count -eq 0) {
        Write-Fail 'Release manifest must contain SHA-256 integrity entries.'
        $script:Failed = $true
    } else {
        foreach ($entry in $integrityFiles) {
            $relative = [string](Get-ObjectPropertyValue -Object $entry -Name 'path' -Default '')
            $expected = [string](Get-ObjectPropertyValue -Object $entry -Name 'sha256' -Default '')
            $path = Join-Path $script:BundleRoot $relative
            if (-not $relative -or -not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected.ToLowerInvariant()) {
                Write-Fail "Manifest integrity mismatch: $relative"
                $script:Failed = $true
            }
        }
    }
}

function Get-NormalizedMediaPipelineReleaseVersion {
    param([Parameter(Mandatory = $true)][string]$Value)

    if ($Value -notmatch '^(?<major>\d+)\.(?<minor>\d+)\.(?<patch>\d+)(?:[.+](?<build>\d+))?$') {
        throw "Release version is not normalized or parseable: $Value"
    }
    $build = if ($Matches['build']) { [int]$Matches['build'] } else { 0 }
    return ('{0}.{1}.{2}+{3:D3}' -f [int]$Matches['major'], [int]$Matches['minor'], [int]$Matches['patch'], $build)
}

function Test-ReleaseContentPrivacy {
    param([Parameter(Mandatory = $true)][string]$ManifestPath)

    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { return }
    if (-not (. Import-MediaPipelineReleasePolicy)) { return }
    $extensions = @('.bat', '.cmd', '.css', '.html', '.js', '.json', '.md', '.ps1', '.psd1', '.py', '.rs', '.toml', '.txt', '.yaml', '.yml')
    $findings = [System.Collections.Generic.List[string]]::new()
    foreach ($file in @(Get-ChildItem -LiteralPath $script:BundleRoot -Force -Recurse -File)) {
        if ($extensions -notcontains $file.Extension.ToLowerInvariant()) { continue }
        $relative = $file.FullName.Substring($script:BundleRoot.Length).TrimStart('\', '/') -replace '/', '\'
        if (-not (Test-MediaPipelineReleaseContentScanEligible -RelativePath $relative)) { continue }
        try {
            $finding = Find-MediaPipelineReleaseContentFinding -RelativePath $relative -Content (Get-Content -LiteralPath $file.FullName -Raw)
        } catch {
            $finding = "could not scan content: $($_.Exception.Message)"
        }
        if ($finding) { $findings.Add([string]$finding) }
    }
    if ($findings.Count -gt 0) {
        Write-Fail ('Release content privacy violations: ' + ($findings -join '; '))
        $script:Failed = $true
    } else {
        Write-Ok 'Included text content passed release privacy policy.'
    }
}

function Test-ReleaseVersionConsistency {
    Write-Section 'Release Identity'
    $versionPath = Join-Path $script:BundleRoot 'ops\release\metadata\VERSION'
    $pyprojectPath = Join-Path $script:BundleRoot 'pyproject.toml'
    $cargoPath = Join-Path $script:BundleRoot 'apps\desktop\tauri\src-tauri\Cargo.toml'
    $tauriConfigPath = Join-Path $script:BundleRoot 'apps\desktop\tauri\src-tauri\tauri.conf.json'
    $packagePath = Join-Path $script:BundleRoot 'apps\desktop\tauri\package.json'
    foreach ($path in @($versionPath, $pyprojectPath, $cargoPath, $tauriConfigPath, $packagePath)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            Write-Fail "Release identity file missing: $path"
            $script:Failed = $true
            return
        }
    }
    try {
        $expected = Get-NormalizedMediaPipelineReleaseVersion -Value (Get-Content -LiteralPath $versionPath -Raw).Trim()
        $pyproject = [regex]::Match((Get-Content -LiteralPath $pyprojectPath -Raw), '(?m)^version\s*=\s*"(?<value>[^"]+)"').Groups['value'].Value
        $cargo = [regex]::Match((Get-Content -LiteralPath $cargoPath -Raw), '(?m)^version\s*=\s*"(?<value>[^"]+)"').Groups['value'].Value
        $tauri = (Get-Content -LiteralPath $tauriConfigPath -Raw | ConvertFrom-Json).version
        $package = (Get-Content -LiteralPath $packagePath -Raw | ConvertFrom-Json).version
        foreach ($entry in @($pyproject, $cargo, $tauri, $package)) {
            if ((Get-NormalizedMediaPipelineReleaseVersion -Value ([string]$entry)) -ne $expected) {
                throw "Version mismatch: expected $expected, found $entry"
            }
        }
        Write-Ok "Normalized version is consistent: $expected"
    } catch {
        Write-Fail "Release identity check failed: $($_.Exception.Message)"
        $script:Failed = $true
    }
}
