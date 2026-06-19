[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('beta', 'stable')]
    [string]$Channel,

    [Parameter(Mandatory)]
    [string]$BundleRoot,

    [Parameter(Mandatory)]
    [string]$Repository,

    [Parameter(Mandatory)]
    [string]$ReleaseTag,

    [Parameter(Mandatory)]
    [string]$Version,

    [switch]$SkipAuthenticode,

    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

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

function Get-FirstFile {
    param(
        [string]$Root,
        [string]$Filter
    )
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        return $null
    }
    return Get-ChildItem -LiteralPath $Root -Filter $Filter -File |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
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

$nsisRoot = Join-Path $BundleRoot 'nsis'
$installer = Get-FirstFile -Root $nsisRoot -Filter '*.exe'
$signaturePath = if ($installer) { "$($installer.FullName).sig" } else { $null }
$channelJsonPath = Join-Path $BundleRoot ("latest-{0}.json" -f $Channel)
$checksumPath = Join-Path $BundleRoot 'SHA256SUMS.txt'

$artifactEvidence = [ordered]@{
    bundle_root = $BundleRoot
    nsis_root = $nsisRoot
    installer = if ($installer) { $installer.FullName } else { $null }
    updater_signature = $signaturePath
    channel_json = $channelJsonPath
    checksums = $checksumPath
    authenticode_status = $null
    msi_artifacts_found = 0
}

Add-Check 'bundle_root' (Test-Path -LiteralPath $BundleRoot -PathType Container) `
    'Bundle root must exist.'
Add-Check 'nsis_root' (Test-Path -LiteralPath $nsisRoot -PathType Container) `
    'NSIS bundle folder must exist.'
Add-Check 'installer' ($null -ne $installer) `
    'At least one NSIS installer .exe must be present.'

$msiArtifacts = @()
if (Test-Path -LiteralPath $BundleRoot -PathType Container) {
    $msiArtifacts = @(Get-ChildItem -LiteralPath $BundleRoot -Filter '*.msi' -File -Recurse)
}
$artifactEvidence.msi_artifacts_found = $msiArtifacts.Count
Add-Check 'msi_disabled' ($msiArtifacts.Count -eq 0) `
    'MSI artifacts must not be present for the first private beta lane.'

$signatureText = $null
if ($signaturePath) {
    Add-Check 'updater_signature:file' (Test-Path -LiteralPath $signaturePath -PathType Leaf) `
        'Updater .sig file must exist beside the NSIS installer.'
    if (Test-Path -LiteralPath $signaturePath -PathType Leaf) {
        $signatureText = (Get-Content -LiteralPath $signaturePath -Raw).Trim()
        Add-Check 'updater_signature:not_empty' (-not [string]::IsNullOrWhiteSpace($signatureText)) `
            'Updater signature file must not be empty.'
    }
}

Add-Check 'channel_json:file' (Test-Path -LiteralPath $channelJsonPath -PathType Leaf) `
    'Updater channel JSON must exist at the bundle root.'

$channelPayload = $null
if (Test-Path -LiteralPath $channelJsonPath -PathType Leaf) {
    try {
        $channelPayload = Get-Content -LiteralPath $channelJsonPath -Raw | ConvertFrom-Json -Depth 20
        $platform = $channelPayload.platforms.'windows-x86_64'
        $expectedUrl = if ($installer) { "https://github.com/$Repository/releases/download/$ReleaseTag/$($installer.Name)" } else { $null }
        Add-Check 'channel_json:version' ([string]$channelPayload.version -eq $Version) `
            'Updater channel JSON version must match the workflow input.'
        Add-Check 'channel_json:url' ($expectedUrl -and [string]$platform.url -eq $expectedUrl) `
            'Updater channel JSON URL must point at the selected GitHub Release asset.'
        Add-Check 'channel_json:signature' (-not [string]::IsNullOrWhiteSpace([string]$platform.signature)) `
            'Updater channel JSON must include windows-x86_64.signature.'
        Add-Check 'channel_json:signature_matches_file' ($signatureText -and [string]$platform.signature -eq $signatureText) `
            'Updater channel JSON signature must match the installer .sig file.'
    } catch {
        Add-Check 'channel_json:parse' $false "Updater channel JSON could not be parsed: $($_.Exception.Message)"
    }
}

Add-Check 'checksums:file' (Test-Path -LiteralPath $checksumPath -PathType Leaf) `
    'SHA256SUMS.txt must exist at the bundle root.'
if (Test-Path -LiteralPath $checksumPath -PathType Leaf) {
    $checksumLines = @(Get-Content -LiteralPath $checksumPath)
    if ($installer) {
        Add-Check 'checksums:installer' (Test-ChecksumLine -Lines $checksumLines -Path $installer.FullName) `
            'SHA256SUMS.txt must include the installer hash.'
    }
    if ($signaturePath) {
        Add-Check 'checksums:signature' (Test-ChecksumLine -Lines $checksumLines -Path $signaturePath) `
            'SHA256SUMS.txt must include the updater signature hash.'
    }
    Add-Check 'checksums:channel_json' (Test-ChecksumLine -Lines $checksumLines -Path $channelJsonPath) `
        'SHA256SUMS.txt must include the updater channel JSON hash.'
}

if ($installer) {
    if ($SkipAuthenticode) {
        Add-Check 'authenticode:skipped' $true `
            'Authenticode validation was skipped by explicit test-only flag.' 'warning'
    } else {
        try {
            $authenticode = Get-AuthenticodeSignature -LiteralPath $installer.FullName
            $artifactEvidence.authenticode_status = [string]$authenticode.Status
            Add-Check 'authenticode:valid' ($authenticode.Status -eq 'Valid') `
                'NSIS installer Authenticode signature must be valid.'
        } catch {
            Add-Check 'authenticode:valid' $false "Authenticode validation failed: $($_.Exception.Message)"
        }
    }
}

$errorCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'error' }).Count
$warningCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'warning' }).Count
$result = [pscustomobject][ordered]@{
    schema_version = 'private_beta_release_artifact_verification.v1'
    ok = ($errorCount -eq 0)
    channel = $Channel
    version = $Version
    release_tag = $ReleaseTag
    repository = $Repository
    artifacts = $artifactEvidence
    error_count = $errorCount
    warning_count = $warningCount
    checks = @($checks)
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 12
} else {
    if ($result.ok) {
        Write-Host "Private beta release artifact verification passed for $Channel $Version."
    } else {
        Write-Host "Private beta release artifact verification failed for $Channel $Version."
    }
    foreach ($check in $checks) {
        $prefix = if ($check.ok) { 'PASS' } elseif ($check.severity -eq 'warning') { 'WARN' } else { 'FAIL' }
        Write-Host ("[{0}] {1}: {2}" -f $prefix, $check.name, $check.message)
    }
}

if (-not $result.ok) {
    exit 1
}
