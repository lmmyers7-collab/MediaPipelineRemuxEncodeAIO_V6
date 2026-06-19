[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$DownloadRoot,

    [ValidateSet('beta', 'stable')]
    [string]$Channel = 'beta',

    [string]$Repository = $env:GITHUB_REPOSITORY,

    [string]$Version = $(if ($env:MEDIAPIPELINE_SEMVER_VERSION) { $env:MEDIAPIPELINE_SEMVER_VERSION } else { '2026.6.4+001' }),

    [string]$ReleaseTag,

    [switch]$SkipAuthenticode,

    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

if (-not $ReleaseTag) {
    $ReleaseTag = "app-v$Version"
}

$checks = [System.Collections.Generic.List[object]]::new()

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

function Get-DownloadedFiles {
    param(
        [string]$Root,
        [string]$Filter
    )
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        return @()
    }
    return @(Get-ChildItem -LiteralPath $Root -Filter $Filter -File | Sort-Object Name)
}

function Test-ChecksumLine {
    param(
        [string[]]$Lines,
        [string]$Path
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    $hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    $leaf = [regex]::Escape((Split-Path -Leaf $Path))
    return [bool]($Lines | Where-Object { $_ -match ("^\s*{0}\s+{1}\s*$" -f $hash, $leaf) } | Select-Object -First 1)
}

function Test-NonEmptyFile {
    param([string]$Path)
    return (Test-Path -LiteralPath $Path -PathType Leaf) -and ((Get-Item -LiteralPath $Path).Length -gt 0)
}

$downloadRootFull = [System.IO.Path]::GetFullPath($DownloadRoot)
$channelJsonName = "latest-$Channel.json"
$channelJsonPath = Join-Path $downloadRootFull $channelJsonName
$checksumPath = Join-Path $downloadRootFull 'SHA256SUMS.txt'

$installerCandidates = @(Get-DownloadedFiles -Root $downloadRootFull -Filter '*.exe')
$installer = $installerCandidates | Select-Object -First 1
$signaturePath = if ($installer) { Join-Path $downloadRootFull "$($installer.Name).sig" } else { $null }
$msiArtifacts = @(Get-DownloadedFiles -Root $downloadRootFull -Filter '*.msi')

$evidence = [ordered]@{
    download_root = $downloadRootFull
    installer = if ($installer) { $installer.FullName } else { $null }
    installer_candidates = @($installerCandidates | ForEach-Object { $_.Name })
    updater_signature = $signaturePath
    channel_json = $channelJsonPath
    checksums = $checksumPath
    msi_artifacts_found = $msiArtifacts.Count
    authenticode_status = $null
}

Add-Check 'download_root' (Test-Path -LiteralPath $downloadRootFull -PathType Container) `
    'Download folder must exist.'
Add-Check 'repository:format' ($Repository -match '^[^/\s]+/[^/\s]+$') `
    'Repository must be owner/repo.'
Add-Check 'version:format' ($Version -match '^\d+\.\d+\.\d+\+\d+$') `
    'Version must be Tauri-compatible semver with build metadata, for example 2026.6.4+001.'
Add-Check 'release_tag:format' ($ReleaseTag -match '^app-v\d+\.\d+\.\d+\+\d+$') `
    'Release tag must use app-v<version>.'
Add-Check 'installer:present' ($installerCandidates.Count -ge 1) `
    'Downloaded assets must include the signed NSIS installer .exe.'
Add-Check 'installer:single' ($installerCandidates.Count -eq 1) `
    'Downloaded folder should contain exactly one installer .exe for the selected release.' 'warning'
if ($installer) {
    Add-Check 'installer:not_empty' (Test-NonEmptyFile -Path $installer.FullName) `
        'Downloaded installer must not be empty.'
    Add-Check 'installer:version_in_name' ([string]$installer.Name -match [regex]::Escape($Version)) `
        'Downloaded installer filename should include the requested version.' 'warning'
}
Add-Check 'msi_disabled' ($msiArtifacts.Count -eq 0) `
    'MSI artifacts must not be present in the first private beta downloaded asset set.'

$signatureText = $null
if ($signaturePath) {
    Add-Check 'updater_signature:file' (Test-Path -LiteralPath $signaturePath -PathType Leaf) `
        'Downloaded assets must include the updater .exe.sig file beside the installer.'
    if (Test-Path -LiteralPath $signaturePath -PathType Leaf) {
        $signatureText = (Get-Content -LiteralPath $signaturePath -Raw).Trim()
        Add-Check 'updater_signature:not_empty' (-not [string]::IsNullOrWhiteSpace($signatureText)) `
            'Updater signature file must not be empty.'
    }
}

Add-Check 'channel_json:file' (Test-Path -LiteralPath $channelJsonPath -PathType Leaf) `
    "Downloaded assets must include $channelJsonName."

$channelPayload = $null
if (Test-Path -LiteralPath $channelJsonPath -PathType Leaf) {
    try {
        $channelPayload = Get-Content -LiteralPath $channelJsonPath -Raw | ConvertFrom-Json -Depth 20
        $platform = $channelPayload.platforms.'windows-x86_64'
        $expectedUrl = if ($installer) { "https://github.com/$Repository/releases/download/$ReleaseTag/$($installer.Name)" } else { $null }
        Add-Check 'channel_json:version' ([string]$channelPayload.version -eq $Version) `
            'Updater channel JSON version must match the selected release version.'
        Add-Check 'channel_json:url' ($expectedUrl -and [string]$platform.url -eq $expectedUrl) `
            'Updater channel JSON URL must point at the downloaded installer release asset.'
        Add-Check 'channel_json:signature' (-not [string]::IsNullOrWhiteSpace([string]$platform.signature)) `
            'Updater channel JSON must include windows-x86_64.signature.'
        Add-Check 'channel_json:signature_matches_file' ($signatureText -and [string]$platform.signature -eq $signatureText) `
            'Updater channel JSON signature must match the downloaded installer .sig file.'
    } catch {
        Add-Check 'channel_json:parse' $false "Updater channel JSON could not be parsed: $($_.Exception.Message)"
    }
}

Add-Check 'checksums:file' (Test-Path -LiteralPath $checksumPath -PathType Leaf) `
    'Downloaded assets must include SHA256SUMS.txt.'
if (Test-Path -LiteralPath $checksumPath -PathType Leaf) {
    $checksumLines = @(Get-Content -LiteralPath $checksumPath)
    if ($installer) {
        Add-Check 'checksums:installer' (Test-ChecksumLine -Lines $checksumLines -Path $installer.FullName) `
            'SHA256SUMS.txt must match the downloaded installer hash.'
    }
    if ($signaturePath) {
        Add-Check 'checksums:signature' (Test-ChecksumLine -Lines $checksumLines -Path $signaturePath) `
            'SHA256SUMS.txt must match the downloaded updater signature hash.'
    }
    Add-Check 'checksums:channel_json' (Test-ChecksumLine -Lines $checksumLines -Path $channelJsonPath) `
        'SHA256SUMS.txt must match the downloaded updater channel JSON hash.'
}

if ($installer) {
    if ($SkipAuthenticode) {
        Add-Check 'authenticode:skipped' $true `
            'Authenticode validation was skipped by explicit test-only flag.' 'warning'
    } else {
        try {
            $authenticode = Get-AuthenticodeSignature -LiteralPath $installer.FullName
            $evidence.authenticode_status = [string]$authenticode.Status
            Add-Check 'authenticode:valid' ($authenticode.Status -eq 'Valid') `
                'Downloaded NSIS installer Authenticode signature must be valid before installation.'
        } catch {
            Add-Check 'authenticode:valid' $false "Authenticode validation failed: $($_.Exception.Message)"
        }
    }
}

$errorCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'error' }).Count
$warningCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'warning' }).Count
$result = [pscustomobject][ordered]@{
    schema_version = 'private_beta_downloaded_asset_verification.v1'
    ok = ($errorCount -eq 0)
    channel = $Channel
    version = $Version
    release_tag = $ReleaseTag
    repository = $Repository
    artifacts = $evidence
    error_count = $errorCount
    warning_count = $warningCount
    checks = @($checks)
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 12
} else {
    if ($result.ok) {
        Write-Host "Private beta downloaded asset verification passed for $Channel $Version."
    } else {
        Write-Host "Private beta downloaded asset verification failed for $Channel $Version."
    }
    foreach ($check in $checks) {
        $prefix = if ($check.ok) { 'PASS' } elseif ($check.severity -eq 'warning') { 'WARN' } else { 'FAIL' }
        Write-Host ("[{0}] {1}: {2}" -f $prefix, $check.name, $check.message)
    }
}

if (-not $result.ok) {
    exit 1
}
