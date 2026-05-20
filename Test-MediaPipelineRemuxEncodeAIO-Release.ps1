[CmdletBinding()]
param(
    [string]$BundleRoot,
    [switch]$RequireTests,
    [switch]$SkipToolIntegration,
    [switch]$SkipEndToEndSmoke
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Write-Section {
    param([string]$Title)
    $bar = '=' * 72
    Write-Host ''
    Write-Host $bar -ForegroundColor Cyan
    Write-Host " $Title" -ForegroundColor Cyan
    Write-Host $bar -ForegroundColor Cyan
}

function Write-Ok   { param([string]$Message) Write-Host "[ OK ] $Message" -ForegroundColor Green }
function Write-Warn { param([string]$Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Fail { param([string]$Message) Write-Host "[FAIL] $Message" -ForegroundColor Red }

function Resolve-ReleasePowerShell {
    param([Parameter(Mandatory = $true)][string]$Root)

    $bundled = Join-Path $Root 'Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe'
    if (Test-Path -LiteralPath $bundled -PathType Leaf) {
        return (Resolve-Path -LiteralPath $bundled).Path
    }

    $cmd = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }

    return $null
}

function Test-PowerShellParse {
    param([Parameter(Mandatory = $true)][string]$Path)

    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors)
    if ($errors.Count -gt 0) {
        throw "PowerShell parse failed for ${Path}: $($errors[0])"
    }
}

function Invoke-ReleaseScriptProcess {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [string[]]$Arguments = @(),
        [int]$TimeoutSeconds = 600
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $script:Pwsh
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    foreach ($argument in @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ScriptPath) + $Arguments) {
        [void]$startInfo.ArgumentList.Add($argument)
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $timedOut = $false
    $stdout = ''
    $stderr = ''

    try {
        [void]$process.Start()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $waitMilliseconds = [Math]::Max(1, $TimeoutSeconds) * 1000
        $exited = $process.WaitForExit($waitMilliseconds)

        if (-not $exited) {
            $timedOut = $true
            try {
                $process.Kill($true)
            } catch {
                try { $process.Kill() } catch { }
            }
            try { [void]$process.WaitForExit(5000) } catch { }
        } else {
            $process.WaitForExit()
        }

        try { $stdout = $stdoutTask.GetAwaiter().GetResult() } catch { $stdout = "[release-check stdout read failed] $($_.Exception.Message)" }
        try { $stderr = $stderrTask.GetAwaiter().GetResult() } catch { $stderr = "[release-check stderr read failed] $($_.Exception.Message)" }

        $output = @()
        foreach ($text in @($stdout, $stderr)) {
            if (-not [string]::IsNullOrEmpty($text)) {
                $output += @($text -split "\r?\n" | Where-Object { $_ -ne '' })
            }
        }

        $exitCode = $null
        if (-not $timedOut -and $process.HasExited) {
            $exitCode = $process.ExitCode
        }

        return [pscustomobject]@{
            ExitCode = $exitCode
            TimedOut = $timedOut
            Output = $output
            StartError = $null
        }
    } catch {
        return [pscustomobject]@{
            ExitCode = $null
            TimedOut = $false
            Output = @()
            StartError = $_.Exception.Message
        }
    } finally {
        if ($process) { $process.Dispose() }
    }
}

function Invoke-ReleaseScriptCheck {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [string[]]$Arguments = @(),
        [switch]$Required,
        [switch]$ShowWarningsOnSuccess,
        [int]$TimeoutSeconds = 600
    )

    if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
        if ($Required) {
            Write-Fail "$Label script is missing: $ScriptPath"
            $script:Failed = $true
        } else {
            Write-Warn "$Label skipped; script is not present: $ScriptPath"
        }
        return
    }

    Write-Host "Running $Label (timeout ${TimeoutSeconds}s)..." -ForegroundColor DarkGray
    $result = Invoke-ReleaseScriptProcess -ScriptPath $ScriptPath -Arguments $Arguments -TimeoutSeconds $TimeoutSeconds
    $output = @($result.Output)

    if ($result.StartError) {
        Write-Fail "$Label could not be started: $($result.StartError)"
        $script:Failed = $true
        return
    }

    if ($result.TimedOut) {
        Write-Fail "$Label timed out after $TimeoutSeconds second(s). Child process tree was terminated."
        $script:Failed = $true
        $output | Select-Object -Last 80 | ForEach-Object { Write-Host $_ }
        return
    }

    $exitCode = $result.ExitCode
    if ($exitCode -eq 0) {
        if ($ShowWarningsOnSuccess) {
            $output | Where-Object { $_ -match '^\[WARN\]' } | ForEach-Object { Write-Host $_ -ForegroundColor Yellow }
        }
        Write-Ok "$Label passed."
        return
    }

    Write-Fail "$Label failed with exit $exitCode."
    $script:Failed = $true
    $output | Select-Object -Last 80 | ForEach-Object { Write-Host $_ }
}

function Get-ObjectPropertyValue {
    param(
        $Object,
        [Parameter(Mandatory = $true)][string]$Name,
        $Default = $null
    )

    if ($null -eq $Object) { return $Default }
    $property = $Object.PSObject.Properties[$Name]
    if ($property) { return $property.Value }
    return $Default
}

function ConvertTo-ReleaseBool {
    param(
        $Value,
        [bool]$Default = $false
    )

    if ($Value -is [bool]) { return [bool]$Value }
    if ($null -eq $Value) { return $Default }
    $text = ([string]$Value).Trim().ToLowerInvariant()
    if ($text -in @('true','1','yes','y','on')) { return $true }
    if ($text -in @('false','0','no','n','off')) { return $false }
    return $Default
}

function Import-MediaPipelineReleasePolicy {
    $policyPath = Join-Path $script:BundleRoot 'Pipeline\Modules\ReleasePolicy.ps1'
    if (-not (Test-Path -LiteralPath $policyPath -PathType Leaf)) {
        Write-Fail "Release policy module missing: $policyPath"
        $script:Failed = $true
        return $false
    }

    try {
        . $policyPath
        return $true
    } catch {
        Write-Fail "Release policy module could not be loaded: $($_.Exception.Message)"
        $script:Failed = $true
        return $false
    }
}

function Assert-ReleasePathAbsent {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $full = Join-Path $script:BundleRoot $RelativePath
    if (Test-Path -LiteralPath $full) {
        Write-Fail "$Label should be absent from a clean release: $RelativePath"
        $script:Failed = $true
    } else {
        Write-Ok "$Label absent: $RelativePath"
    }
}

function Assert-ReleasePathPresent {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $full = Join-Path $script:BundleRoot $RelativePath
    if (Test-Path -LiteralPath $full -PathType Leaf) {
        Write-Ok "$Label present: $RelativePath"
    } else {
        Write-Fail "$Label should be present in this release: $RelativePath"
        $script:Failed = $true
    }
}

function Assert-ReleasePatternAbsent {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePattern,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $pattern = Join-Path $script:BundleRoot $RelativePattern
    $matches = @(Get-ChildItem -Path $pattern -Force -ErrorAction SilentlyContinue)
    if ($matches.Count -gt 0) {
        Write-Fail "$Label should be absent from a clean release: $RelativePattern"
        $matches | Select-Object -First 8 | ForEach-Object { Write-Host "  $($_.FullName)" }
        if ($matches.Count -gt 8) { Write-Host ("  ...and {0} more" -f ($matches.Count - 8)) }
        $script:Failed = $true
    } else {
        Write-Ok "$Label absent: $RelativePattern"
    }
}

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

    $launcherPath = Join-Path $script:BundleRoot 'DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1'
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
        @{ Pattern = 'Token auth: enabled \(browser receives a per-run bootstrap token\)'; Label = 'default token-enabled operator banner' },
        @{ Pattern = 'Token auth: DISABLED by explicit -NoTokenDevMode'; Label = 'explicit no-token warning banner' },
        @{ Pattern = 'if \(\$NoTokenDevMode\)[\s\S]+?\$apiArgs \+= ''--no-token'''; Label = 'no-token argument gated by NoTokenDevMode' }
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
        Write-Warn 'release_manifest.json not found. Manifest hygiene checks are skipped for source/dev folders.'
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
}

$script:BundleRoot = if ($BundleRoot) {
    [System.IO.Path]::GetFullPath($BundleRoot)
} elseif ($PSScriptRoot) {
    [System.IO.Path]::GetFullPath($PSScriptRoot)
} else {
    [System.IO.Path]::GetFullPath((Get-Location).Path)
}

$script:Pwsh = Resolve-ReleasePowerShell -Root $script:BundleRoot
$script:Failed = $false

$pipelineRoot = Join-Path $script:BundleRoot 'Pipeline'
$testsRoot = Join-Path $pipelineRoot 'Tests'
$verifier = Join-Path $script:BundleRoot 'Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1'
$tauriPrereqs = Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\Test-TauriShell-Prereqs.ps1'
$v6Reliability = Join-Path $testsRoot 'Invoke-V6WebViewReliabilityChecks.ps1'
$toolIntegration = Join-Path $testsRoot 'Invoke-ToolIntegrationChecks.ps1'
$endToEndSmoke = Join-Path $testsRoot 'Invoke-EndToEndSmokeChecks.ps1'
$releaseManifest = Join-Path $script:BundleRoot 'release_manifest.json'

Write-Section 'Release Self-Test'
Write-Host "Bundle root : $script:BundleRoot"
if ($script:Pwsh) {
    Write-Ok "PowerShell host: $script:Pwsh"
} else {
    Write-Fail 'PowerShell 7 host not found. Cannot run release checks.'
    exit 1
}

Write-Section 'Layout'
foreach ($entry in @(
    @{ Label = 'DesktopApp'; Path = (Join-Path $script:BundleRoot 'DesktopApp'); Type = 'Container' },
    @{ Label = 'Docs'; Path = (Join-Path $script:BundleRoot 'Docs'); Type = 'Container' },
    @{ Label = 'Pipeline'; Path = $pipelineRoot; Type = 'Container' },
    @{ Label = 'SmokeTests'; Path = (Join-Path $script:BundleRoot 'SmokeTests'); Type = 'Container' },
    @{ Label = 'Docs index'; Path = (Join-Path $script:BundleRoot 'Docs\DOCS_INDEX.md'); Type = 'Leaf' },
    @{ Label = 'Bundle README'; Path = (Join-Path $script:BundleRoot 'Docs\README_MediaPipelineRemuxEncodeAIO.md'); Type = 'Leaf' },
    @{ Label = 'Operator TLDR'; Path = (Join-Path $script:BundleRoot 'Docs\TLDR.md'); Type = 'Leaf' },
    @{ Label = 'Smoke test inventory'; Path = (Join-Path $script:BundleRoot 'Docs\inventories\SMOKE_TEST_INVENTORY.md'); Type = 'Leaf' },
    @{ Label = 'Desktop/WebView docs README'; Path = (Join-Path $script:BundleRoot 'Docs\DesktopApp\docs\README.md'); Type = 'Leaf' },
    @{ Label = 'Release package inventory'; Path = (Join-Path $script:BundleRoot 'Docs\inventories\RELEASE_PACKAGE_ADMIN_INVENTORY.md'); Type = 'Leaf' },
    @{ Label = 'Root setup launcher'; Path = (Join-Path $script:BundleRoot 'Setup-MediaPipelineRemuxEncodeAIO.bat'); Type = 'Leaf' },
    @{ Label = 'Root run launcher'; Path = (Join-Path $script:BundleRoot 'Run-MediaPipelineRemuxEncodeAIO.bat'); Type = 'Leaf' },
    @{ Label = 'Root API and browser launcher'; Path = (Join-Path $script:BundleRoot 'Start-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.bat'); Type = 'Leaf' },
    @{ Label = 'Root local API launcher'; Path = (Join-Path $script:BundleRoot 'Start-MediaPipelineRemuxEncodeAIO-LocalApi.bat'); Type = 'Leaf' },
    @{ Label = 'Root Tauri preview launcher'; Path = (Join-Path $script:BundleRoot 'Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat'); Type = 'Leaf' },
    @{ Label = 'Root real-media validation worksheet helper'; Path = (Join-Path $script:BundleRoot 'New-RealMediaValidationWorksheet.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView evidence smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewRealMediaEvidenceSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView command evidence smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewCommandEvidenceSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView row detail smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewRowDetailSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView schedule smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewScheduleSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView browser schedule smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewBrowserScheduleSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView browser backend lifecycle smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewBrowserLifecycleSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests local API lifecycle contract smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-LocalApiLifecycleContractSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests local API Maintenance dry-run contract smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-LocalApiMaintenanceDryRunContractSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests local API sample validation contract smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-LocalApiSampleValidationContractSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView browser high-risk smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewBrowserHighRiskSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView browser diagnostics handoff smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView browser pending drain guard smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewBrowserPendingDrainGuardSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView browser completed pending proof smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewBrowserCompletedPendingProofSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView browser large daily-table smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewBrowserLargeTableSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView browser rename smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewBrowserRenameSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView browser network smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewBrowserNetworkSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView browser telemetry smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewBrowserTelemetrySmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView browser Maintenance/Reports smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewBrowserMaintenanceReportsSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView browser Sample Validation smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewBrowserSampleValidationSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView browser Home live-state smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewBrowserHomeLiveStateSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView browser Launch/Queue readiness smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView browser layout manager smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewBrowserLayoutManagerSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView rename readiness smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewRenameReadinessSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView browser settings/launch smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewBrowserSettingsLaunchSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView settings launch policy smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewSettingsLaunchPolicySmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView settings live-config smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewSettingsLaunchLiveConfigSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'SmokeTests WebView settings patch evidence smoke'; Path = (Join-Path $script:BundleRoot 'SmokeTests\Test-WebViewSettingsPatchEvidenceSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'V6 reliability compatibility wrapper'; Path = (Join-Path $pipelineRoot 'Tests\Invoke-ReliabilityRegressionChecks.ps1'); Type = 'Leaf'; Required = [bool]$RequireTests },
    @{ Label = 'V6 WebView reliability gate'; Path = $v6Reliability; Type = 'Leaf'; Required = [bool]$RequireTests },
    @{ Label = 'Native process cleanup unit gate'; Path = (Join-Path $pipelineRoot 'Tests\Unit\Invoke-NativeProcessCleanupChecks.ps1'); Type = 'Leaf'; Required = [bool]$RequireTests },
    @{ Label = 'Runtime state hygiene unit gate'; Path = (Join-Path $pipelineRoot 'Tests\Unit\Invoke-RuntimeStateHygieneChecks.ps1'); Type = 'Leaf'; Required = [bool]$RequireTests },
    @{ Label = 'Release policy module'; Path = (Join-Path $pipelineRoot 'Modules\ReleasePolicy.ps1'); Type = 'Leaf' },
    @{ Label = 'Desktop local API launcher'; Path = (Join-Path $script:BundleRoot 'DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat'); Type = 'Leaf' },
    @{ Label = 'Environment verifier'; Path = $verifier; Type = 'Leaf' },
    @{ Label = 'Config template'; Path = (Join-Path $pipelineRoot 'MediaPipeline_config_template.psd1'); Type = 'Leaf' },
    @{ Label = 'ASS to SRT helper'; Path = (Join-Path $pipelineRoot 'ass_to_srt_chatgpt.py'); Type = 'Leaf' },
    @{ Label = 'Application DTO compatibility exports'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\dto.py'); Type = 'Leaf' },
    @{ Label = 'Application DTO base helpers'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\dto_base.py'); Type = 'Leaf' },
    @{ Label = 'Application command DTOs'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\dto_commands.py'); Type = 'Leaf' },
    @{ Label = 'Application inventory DTOs'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\dto_inventory.py'); Type = 'Leaf' },
    @{ Label = 'Application status DTOs'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\dto_status.py'); Type = 'Leaf' },
    @{ Label = 'Application workspace DTOs'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\dto_workspaces.py'); Type = 'Leaf' },
    @{ Label = 'Application facade'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade audit mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_audit.py'); Type = 'Leaf' },
    @{ Label = 'Application facade completed mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_completed.py'); Type = 'Leaf' },
    @{ Label = 'Application facade completed open mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_completed_open.py'); Type = 'Leaf' },
    @{ Label = 'Application facade diagnostics mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_diagnostics.py'); Type = 'Leaf' },
    @{ Label = 'Application facade failures mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_failures.py'); Type = 'Leaf' },
    @{ Label = 'Application facade inventory mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_inventory.py'); Type = 'Leaf' },
    @{ Label = 'Application facade maintenance mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_maintenance.py'); Type = 'Leaf' },
    @{ Label = 'Application facade maintenance backfill mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_maintenance_backfill.py'); Type = 'Leaf' },
    @{ Label = 'Application facade maintenance commands mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_maintenance_commands.py'); Type = 'Leaf' },
    @{ Label = 'Application facade maintenance release mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_maintenance_release.py'); Type = 'Leaf' },
    @{ Label = 'Application facade pending-publish mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_pending_publish.py'); Type = 'Leaf' },
    @{ Label = 'Application facade process mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_process.py'); Type = 'Leaf' },
    @{ Label = 'Application facade process audit launch mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_process_audit.py'); Type = 'Leaf' },
    @{ Label = 'Application facade process control mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_process_control.py'); Type = 'Leaf' },
    @{ Label = 'Application facade process guard mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_process_guard.py'); Type = 'Leaf' },
    @{ Label = 'Application facade process pipeline launch mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_process_pipeline.py'); Type = 'Leaf' },
    @{ Label = 'Application facade process rerun launch mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_process_rerun.py'); Type = 'Leaf' },
    @{ Label = 'Application facade process schedule mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_process_schedule.py'); Type = 'Leaf' },
    @{ Label = 'Application facade queue mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_queue.py'); Type = 'Leaf' },
    @{ Label = 'Application facade rename mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_rename.py'); Type = 'Leaf' },
    @{ Label = 'Application facade sample validation mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_sample_validation.py'); Type = 'Leaf' },
    @{ Label = 'Application sample validation policy'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_sample_validation_policy.py'); Type = 'Leaf' },
    @{ Label = 'Application facade schedule mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_schedule.py'); Type = 'Leaf' },
    @{ Label = 'Application facade settings mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_settings.py'); Type = 'Leaf' },
    @{ Label = 'Application facade settings helpers mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_settings_helpers.py'); Type = 'Leaf' },
    @{ Label = 'Application facade settings patch mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_settings_patch.py'); Type = 'Leaf' },
    @{ Label = 'Application facade settings patch candidate mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_settings_patch_candidate.py'); Type = 'Leaf' },
    @{ Label = 'Application facade settings risk mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_settings_risk.py'); Type = 'Leaf' },
    @{ Label = 'Application settings risk policy'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\settings_risk_policy.py'); Type = 'Leaf' },
    @{ Label = 'Application facade status mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_status.py'); Type = 'Leaf' },
    @{ Label = 'Application facade utilities mixin'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_utils.py'); Type = 'Leaf' },
    @{ Label = 'Local API command payloads'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_payloads.py'); Type = 'Leaf' },
    @{ Label = 'Local API command payload policy'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_payloads_policy.py'); Type = 'Leaf' },
    @{ Label = 'Local API file command payloads'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_payloads_files.py'); Type = 'Leaf' },
    @{ Label = 'Local API maintenance command payloads'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_payloads_maintenance.py'); Type = 'Leaf' },
    @{ Label = 'Local API process command payloads'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_payloads_process.py'); Type = 'Leaf' },
    @{ Label = 'Local API rename command payloads'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_payloads_rename.py'); Type = 'Leaf' },
    @{ Label = 'Local API sample validation command payloads'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_payloads_sample_validation.py'); Type = 'Leaf' },
    @{ Label = 'Local API settings command payloads'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_payloads_settings.py'); Type = 'Leaf' },
    @{ Label = 'Local API command journal'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_journal.py'); Type = 'Leaf' },
    @{ Label = 'Local API command journal policy'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_journal_policy.py'); Type = 'Leaf' },
    @{ Label = 'Local API command route contract'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\contract_command.py'); Type = 'Leaf' },
    @{ Label = 'Local API route contract'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\contract.py'); Type = 'Leaf' },
    @{ Label = 'Local API route contract payload'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\contract_payload.py'); Type = 'Leaf' },
    @{ Label = 'Local API read route contract'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\contract_read.py'); Type = 'Leaf' },
    @{ Label = 'Local API route contract shared constants'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\contract_shared.py'); Type = 'Leaf' },
    @{ Label = 'Local API HTTP handler'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\handler.py'); Type = 'Leaf' },
    @{ Label = 'Local API HTTP handler policy'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\handler_policy.py'); Type = 'Leaf' },
    @{ Label = 'Local API HTTP helpers'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\http_helpers.py'); Type = 'Leaf' },
    @{ Label = 'Local API read payloads'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\read_payloads.py'); Type = 'Leaf' },
    @{ Label = 'Local API read payload policy'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\read_payloads_policy.py'); Type = 'Leaf' },
    @{ Label = 'Local API inventory read payloads'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\read_payloads_inventory.py'); Type = 'Leaf' },
    @{ Label = 'Local API status read payloads'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\read_payloads_status.py'); Type = 'Leaf' },
    @{ Label = 'Local API workspace read payloads'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\read_payloads_workspace.py'); Type = 'Leaf' },
    @{ Label = 'Local API route handlers'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\routes.py'); Type = 'Leaf' },
    @{ Label = 'Local API command route handlers'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\routes_command.py'); Type = 'Leaf' },
    @{ Label = 'Local API read route handlers'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\routes_read.py'); Type = 'Leaf' },
    @{ Label = 'Local API route handler shared spec'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\routes_shared.py'); Type = 'Leaf' },
    @{ Label = 'Local API static file helpers'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\static_files.py'); Type = 'Leaf' },
    @{ Label = 'Local API static file policy'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\static_files_policy.py'); Type = 'Leaf' },
    @{ Label = 'Local API server'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\server.py'); Type = 'Leaf' },
    @{ Label = 'Headless local API bootstrap helper'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\backend_bootstrap.py'); Type = 'Leaf' },
    @{ Label = 'Headless local API entrypoint'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\local_api_main.py'); Type = 'Leaf' },
    @{ Label = 'Web prototype index'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html'); Type = 'Leaf' },
    @{ Label = 'Web prototype script'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\app.js'); Type = 'Leaf' },
    @{ Label = 'Web prototype styles'; Path = (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\styles.css'); Type = 'Leaf' },
    @{ Label = 'Tauri shell package'; Path = (Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\package.json'); Type = 'Leaf' },
    @{ Label = 'Tauri shell package lock'; Path = (Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\package-lock.json'); Type = 'Leaf' },
    @{ Label = 'Tauri shell preview launcher'; Path = (Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1'); Type = 'Leaf' },
    @{ Label = 'Tauri shell prereq checker'; Path = $tauriPrereqs; Type = 'Leaf' },
    @{ Label = 'Tauri shell build checker'; Path = (Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\Test-TauriShell-Build.ps1'); Type = 'Leaf' },
    @{ Label = 'Tauri shell launch checker'; Path = (Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\Test-TauriShell-Launch.ps1'); Type = 'Leaf' },
    @{ Label = 'Tauri shell PG-3 report helper'; Path = (Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\New-TauriShell-PG3CleanMachineReport.ps1'); Type = 'Leaf' },
    @{ Label = 'Tauri shell config'; Path = (Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\src-tauri\tauri.conf.json'); Type = 'Leaf' },
    @{ Label = 'Tauri shell Cargo manifest'; Path = (Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\src-tauri\Cargo.toml'); Type = 'Leaf' },
    @{ Label = 'Tauri shell Cargo lock'; Path = (Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\src-tauri\Cargo.lock'); Type = 'Leaf' },
    @{ Label = 'Tauri shell Windows icon'; Path = (Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\src-tauri\icons\icon.ico'); Type = 'Leaf' },
    @{ Label = 'Tauri shell launcher source'; Path = (Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\src-tauri\src\lib.rs'); Type = 'Leaf' }
)) {
    $entryRequired = $true
    if ($entry.ContainsKey('Required')) {
        $entryRequired = [bool]$entry.Required
    }
    if (Test-Path -LiteralPath $entry.Path -PathType $entry.Type) {
        Write-Ok "$($entry.Label): $($entry.Path)"
    } elseif ($entryRequired) {
        Write-Fail "$($entry.Label) missing: $($entry.Path)"
        $script:Failed = $true
    } else {
        Write-Warn "$($entry.Label) skipped; optional test file is not present in this package: $($entry.Path)"
    }
}

Test-ReleaseManifestHygiene -ManifestPath $releaseManifest
Test-WebStaticAssetReferences -StaticRoot (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\ui_web\static')
Test-ApiBrowserLauncherTokenPolicy

Write-Section 'Parser Checks'
$parseFiles = @(
    (Join-Path $script:BundleRoot 'Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1'),
    (Join-Path $script:BundleRoot 'Test-MediaPipelineRemuxEncodeAIO-Release.ps1'),
    (Join-Path $script:BundleRoot 'DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1'),
    (Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1'),
    (Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\Test-TauriShell-Prereqs.ps1'),
    (Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\Test-TauriShell-Build.ps1'),
    (Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\Test-TauriShell-Launch.ps1'),
    (Join-Path $script:BundleRoot 'DesktopApp\tauri_shell\New-TauriShell-PG3CleanMachineReport.ps1'),
    (Join-Path $pipelineRoot 'Setup-MediaPipeline_chatgpt.ps1'),
    (Join-Path $pipelineRoot 'MediaPipeline_chatgpt.ps1'),
    (Join-Path $pipelineRoot 'Audit-MediaLibrary_chatgpt.ps1'),
    (Join-Path $pipelineRoot 'Invoke-RerunCsv.ps1'),
    (Join-Path $pipelineRoot 'Backfill-CompletedManifest.ps1')
)
$moduleRoot = Join-Path $pipelineRoot 'Modules'
if (Test-Path -LiteralPath $moduleRoot -PathType Container) {
    $parseFiles += @(Get-ChildItem -LiteralPath $moduleRoot -Filter '*.ps1' -File | ForEach-Object { $_.FullName })
}

foreach ($file in @($parseFiles)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { continue }
    try {
        Test-PowerShellParse -Path $file
    } catch {
        Write-Fail $_.Exception.Message
        $script:Failed = $true
    }
}
if (-not $script:Failed) {
    Write-Ok 'Core PowerShell scripts parse cleanly.'
}

Write-Section 'Python Syntax Checks'
$pythonSyntaxFiles = @(
    (Join-Path $pipelineRoot 'ass_to_srt_chatgpt.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\dto.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\dto_base.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\dto_commands.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\dto_inventory.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\dto_status.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\dto_workspaces.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_audit.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_completed.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_completed_open.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_diagnostics.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_failures.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_inventory.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_maintenance.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_maintenance_backfill.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_maintenance_commands.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_maintenance_release.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_pending_publish.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_process.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_process_audit.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_process_control.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_process_guard.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_process_pipeline.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_process_rerun.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_process_schedule.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_queue.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_rename.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_schedule.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_settings.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_settings_helpers.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_settings_patch.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_settings_patch_candidate.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_settings_risk.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\settings_risk_policy.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_status.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\application\facade_utils.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_payloads.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_payloads_policy.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_payloads_files.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_payloads_maintenance.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_payloads_process.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_payloads_rename.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_payloads_settings.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_journal.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\command_journal_policy.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\contract_command.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\contract.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\contract_payload.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\contract_read.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\contract_shared.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\handler.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\handler_policy.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\http_helpers.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\read_payloads.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\read_payloads_policy.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\read_payloads_inventory.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\read_payloads_status.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\read_payloads_workspace.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\routes.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\routes_command.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\routes_read.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\routes_shared.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\static_files.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\static_files_policy.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\api\server.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\backend_bootstrap.py'),
    (Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app\local_api_main.py')
)
$desktopPackageRoot = Join-Path $script:BundleRoot 'DesktopApp\mediapipeline_desktop_app'
if (Test-Path -LiteralPath $desktopPackageRoot -PathType Container) {
    $pythonSyntaxFiles += @(
        Get-ChildItem -LiteralPath $desktopPackageRoot -Filter '*.py' -File -Recurse |
            ForEach-Object { $_.FullName }
    )
}
$pythonSyntaxFiles = @($pythonSyntaxFiles | Sort-Object -Unique)
$pythonForSyntax = Join-Path $script:BundleRoot 'DesktopApp\Runtime\Python\python.exe'
if (-not (Test-Path -LiteralPath $pythonForSyntax -PathType Leaf)) {
    Write-Fail "Bundled desktop Python missing for syntax checks: $pythonForSyntax"
    $script:Failed = $true
} else {
    $existingPythonSyntaxFiles = @($pythonSyntaxFiles | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf })
    $pythonSyntaxCode = @'
import ast
import pathlib
import sys

failed = False
for raw in sys.stdin.read().splitlines():
    raw = raw.strip()
    if not raw:
        continue
    path = pathlib.Path(raw)
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        print(f"{path}: {exc}", file=sys.stderr)
        failed = True
    except OSError as exc:
        print(f"{path}: {exc}", file=sys.stderr)
        failed = True
raise SystemExit(1 if failed else 0)
'@
    $existingPythonSyntaxFiles | & $pythonForSyntax -c $pythonSyntaxCode
    if ($LASTEXITCODE -ne 0) {
        Write-Fail 'Core Python syntax checks failed.'
        $script:Failed = $true
    } else {
        Write-Ok 'Core Python files parse cleanly.'
    }
}

Write-Section 'Desktop Python Unit Tests'
$desktopTestsRoot = Join-Path $script:BundleRoot 'DesktopApp\tests'
if (-not (Test-Path -LiteralPath $desktopTestsRoot -PathType Container)) {
    if ($RequireTests) {
        Write-Fail "Desktop Python tests are required but missing: $desktopTestsRoot"
        $script:Failed = $true
    } else {
        Write-Warn "Desktop Python tests skipped; tests are not present: $desktopTestsRoot"
    }
} elseif (-not (Test-Path -LiteralPath $pythonForSyntax -PathType Leaf)) {
    Write-Fail "Bundled desktop Python missing for unit tests: $pythonForSyntax"
    $script:Failed = $true
} else {
    Write-Host 'Running desktop Python unit tests...' -ForegroundColor DarkGray
    $previousPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $script:BundleRoot 'DesktopApp'
        Push-Location -LiteralPath $script:BundleRoot
        $desktopTestOutput = & $pythonForSyntax -m unittest discover -s 'DesktopApp\tests' -p 'test_*.py' 2>&1 | ForEach-Object { [string]$_ }
        $desktopTestExit = $LASTEXITCODE
        if ($desktopTestExit -eq 0) {
            Write-Ok 'desktop Python unit tests passed.'
        } else {
            Write-Fail "desktop Python unit tests failed with exit $desktopTestExit."
            $script:Failed = $true
            $desktopTestOutput | Select-Object -Last 80 | ForEach-Object { Write-Host $_ }
        }
    } finally {
        Pop-Location
        $env:PYTHONPATH = $previousPythonPath
    }
}

Write-Section 'Environment'
Invoke-ReleaseScriptCheck -Label 'environment verifier' -ScriptPath $verifier -Required -TimeoutSeconds 300

Write-Section 'Tauri Preview Gate'
Invoke-ReleaseScriptCheck -Label 'Tauri shell preview prerequisites' -ScriptPath $tauriPrereqs -Required -ShowWarningsOnSuccess -TimeoutSeconds 120

Write-Section 'Regression Gates'
$testsPresent = Test-Path -LiteralPath $testsRoot -PathType Container
if (-not $testsPresent) {
    if ($RequireTests) {
        Write-Fail "Tests are required but missing: $testsRoot"
        $script:Failed = $true
    } else {
        Write-Warn "Pipeline tests are not present in this package. Build with -IncludeTests for the full release gate."
    }
} else {
    Invoke-ReleaseScriptCheck -Label 'V6 WebView reliability checks' -ScriptPath $v6Reliability -Required:([bool]$RequireTests) -TimeoutSeconds 600

    if ($SkipToolIntegration) {
        Write-Warn 'Tool integration checks skipped by request.'
    } else {
        Invoke-ReleaseScriptCheck -Label 'tool integration checks' -ScriptPath $toolIntegration -Required:([bool]$RequireTests) -TimeoutSeconds 600
    }

    if ($SkipEndToEndSmoke) {
        Write-Warn 'End-to-end smoke checks skipped by request.'
    } else {
        Invoke-ReleaseScriptCheck -Label 'end-to-end smoke checks' -ScriptPath $endToEndSmoke -Required:([bool]$RequireTests) -TimeoutSeconds 900
    }
}

Write-Section 'Summary'
if ($script:Failed) {
    Write-Fail 'Release self-test failed.'
    exit 1
}

Write-Ok 'Release self-test passed.'

