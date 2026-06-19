[CmdletBinding()]
param(
    [ValidateSet('beta', 'stable')]
    [string]$Channel = 'beta',

    [string]$Repository = $env:GITHUB_REPOSITORY,

    [string]$Version = $(if ($env:MEDIAPIPELINE_SEMVER_VERSION) { $env:MEDIAPIPELINE_SEMVER_VERSION } else { '2026.6.4+001' }),

    [string]$ReleaseTag,

    [string]$ReleaseJsonPath,

    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptRoot))))

if (-not $ReleaseTag) {
    $ReleaseTag = "app-v$Version"
}

$checks = [System.Collections.Generic.List[object]]::new()
$commands = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Message,
        [ValidateSet('error', 'warning')]
        [string]$Severity = 'error'
    )
    $checks.Add([pscustomobject][ordered]@{
        name = $Name
        ok = $Ok
        severity = $Severity
        message = $Message
    }) | Out-Null
}

function Resolve-Tool {
    param([string]$Name)
    foreach ($candidate in @("$Name.exe", "$Name.cmd", $Name)) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command -and $command.Source) {
            if ([System.IO.Path]::GetExtension($command.Source) -ieq '.ps1') {
                $siblingCmd = [System.IO.Path]::ChangeExtension($command.Source, '.cmd')
                if (Test-Path -LiteralPath $siblingCmd -PathType Leaf) {
                    return $siblingCmd
                }
            }
            return $command.Source
        }
    }
    return $null
}

function Invoke-CapturedCommand {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory = $repoRoot
    )
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $FilePath
    foreach ($arg in $Arguments) {
        $psi.ArgumentList.Add($arg)
    }
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $process = [System.Diagnostics.Process]::Start($psi)
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    $commands.Add([pscustomobject][ordered]@{
        name = $Name
        exit_code = $process.ExitCode
        stdout_tail = if ($stdout.Length -gt 3000) { $stdout.Substring($stdout.Length - 3000) } else { $stdout }
        stderr_tail = if ($stderr.Length -gt 3000) { $stderr.Substring($stderr.Length - 3000) } else { $stderr }
    }) | Out-Null
    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        Stdout = $stdout
        Stderr = $stderr
    }
}

function Read-ReleaseJson {
    if ($ReleaseJsonPath) {
        Add-Check 'release_json:file' (Test-Path -LiteralPath $ReleaseJsonPath -PathType Leaf) `
            'Saved GitHub Release JSON fixture must exist.'
        if (-not (Test-Path -LiteralPath $ReleaseJsonPath -PathType Leaf)) {
            return $null
        }
        return Get-Content -LiteralPath $ReleaseJsonPath -Raw
    }

    $gh = Resolve-Tool 'gh'
    Add-Check 'gh:available' ($null -ne $gh) `
        'GitHub CLI must be installed and on PATH when -ReleaseJsonPath is not provided.'
    if (-not $gh) {
        return $null
    }
    $api = Invoke-CapturedCommand -Name 'gh_release_by_tag' -FilePath $gh -Arguments @(
        'api',
        "repos/$Repository/releases/tags/$ReleaseTag"
    )
    Add-Check 'github:release_json' ($api.ExitCode -eq 0) `
        'GitHub Release metadata must be readable through gh api.'
    if ($api.ExitCode -ne 0) {
        return $null
    }
    return $api.Stdout
}

function Select-AssetsByName {
    param(
        [object[]]$Assets,
        [string]$Pattern
    )
    return @($Assets | Where-Object { [string]$_.name -match $Pattern })
}

Add-Check 'repository:format' ($Repository -match '^[^/\s]+/[^/\s]+$') `
    'Repository must be owner/repo.'
Add-Check 'version:format' ($Version -match '^\d+\.\d+\.\d+\+\d+$') `
    'Version must be Tauri-compatible semver with build metadata, for example 2026.6.4+001.'
Add-Check 'release_tag:format' ($ReleaseTag -match '^app-v\d+\.\d+\.\d+\+\d+$') `
    'Release tag must use app-v<version>.'

$releasePayload = $null
$releaseJson = Read-ReleaseJson
if ($releaseJson) {
    try {
        $releasePayload = $releaseJson | ConvertFrom-Json -Depth 20
        Add-Check 'release_json:parse' $true 'GitHub Release JSON parsed.'
    } catch {
        Add-Check 'release_json:parse' $false "GitHub Release JSON could not be parsed: $($_.Exception.Message)"
    }
}

$assets = @()
$assetNames = @()
if ($releasePayload) {
    $assets = @($releasePayload.assets)
    $assetNames = @($assets | ForEach-Object { [string]$_.name })
    $expectedTitle = "MediaPipelineRemuxEncodeAIO $Version ($Channel)"

    Add-Check 'release:tag' ([string]$releasePayload.tag_name -eq $ReleaseTag) `
        'Published GitHub Release tag must match the requested release tag.'
    Add-Check 'release:not_draft' (-not [bool]$releasePayload.draft) `
        'Published GitHub Release must not be a draft before sending beta download links.'
    if ($Channel -eq 'stable') {
        Add-Check 'release:stable_not_prerelease' (-not [bool]$releasePayload.prerelease) `
            'Stable releases must not be marked prerelease.'
    } else {
        Add-Check 'release:beta_prerelease' ([bool]$releasePayload.prerelease) `
            'Beta releases must be marked prerelease.'
    }
    Add-Check 'release:title' ([string]$releasePayload.name -eq $expectedTitle) `
        'Published GitHub Release title must match the workflow-created product/version/channel title.' 'warning'
    Add-Check 'release:notes' (-not [string]::IsNullOrWhiteSpace([string]$releasePayload.body)) `
        'Published GitHub Release must include release notes.'
    Add-Check 'release:asset_count' ($assets.Count -ge 4) `
        'Published GitHub Release must contain at least installer, signature, channel JSON, and checksums assets.'

    $installerAssets = @(Select-AssetsByName -Assets $assets -Pattern '\.exe$')
    $signatureAssets = @(Select-AssetsByName -Assets $assets -Pattern '\.exe\.sig$')
    $channelJsonName = "latest-$Channel.json"
    $channelJsonAssets = @($assets | Where-Object { [string]$_.name -eq $channelJsonName })
    $checksumAssets = @($assets | Where-Object { [string]$_.name -eq 'SHA256SUMS.txt' })
    $msiAssets = @(Select-AssetsByName -Assets $assets -Pattern '\.msi$')

    Add-Check 'assets:installer' ($installerAssets.Count -ge 1) `
        'Published GitHub Release must include the signed NSIS installer .exe asset.'
    Add-Check 'assets:installer_version' ($installerAssets.Count -ge 1 -and [string]$installerAssets[0].name -match [regex]::Escape($Version)) `
        'NSIS installer asset name should include the requested version.' 'warning'
    Add-Check 'assets:updater_signature' ($signatureAssets.Count -ge 1) `
        'Published GitHub Release must include the updater .exe.sig asset.'
    Add-Check 'assets:channel_json' ($channelJsonAssets.Count -eq 1) `
        "Published GitHub Release must include exactly one $channelJsonName asset."
    Add-Check 'assets:checksums' ($checksumAssets.Count -eq 1) `
        'Published GitHub Release must include exactly one SHA256SUMS.txt asset.'
    Add-Check 'assets:no_msi' ($msiAssets.Count -eq 0) `
        'MSI assets must not be published in the first private beta lane.'

    if ($installerAssets.Count -ge 1 -and $signatureAssets.Count -ge 1) {
        $installerName = [string]$installerAssets[0].name
        Add-Check 'assets:signature_matches_installer' ([bool]($signatureAssets | Where-Object { [string]$_.name -eq "$installerName.sig" } | Select-Object -First 1)) `
            'Updater signature asset must be named beside the installer as <installer>.sig.'
    }

    if ($channelJsonAssets.Count -eq 1) {
        $expectedChannelUrl = "https://github.com/$Repository/releases/download/$ReleaseTag/$channelJsonName"
        Add-Check 'assets:channel_json_url' ([string]$channelJsonAssets[0].browser_download_url -eq $expectedChannelUrl) `
            "Channel JSON browser_download_url must match $expectedChannelUrl."
    }
}

$errorCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'error' }).Count
$warningCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'warning' }).Count
$result = [pscustomobject][ordered]@{
    schema_version = 'private_beta_published_release_verification.v1'
    ok = ($errorCount -eq 0)
    channel = $Channel
    version = $Version
    release_tag = $ReleaseTag
    repository = $Repository
    release_json_path = $ReleaseJsonPath
    asset_names = @($assetNames)
    error_count = $errorCount
    warning_count = $warningCount
    checks = @($checks)
    commands = @($commands)
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 12
} else {
    if ($result.ok) {
        Write-Host "Private beta published release verification passed for $Repository $ReleaseTag."
    } else {
        Write-Host "Private beta published release verification failed for $Repository $ReleaseTag."
    }
    foreach ($check in $checks) {
        $prefix = if ($check.ok) { 'PASS' } elseif ($check.severity -eq 'warning') { 'WARN' } else { 'FAIL' }
        Write-Host ("[{0}] {1}: {2}" -f $prefix, $check.name, $check.message)
    }
}

if (-not $result.ok) {
    exit 1
}
