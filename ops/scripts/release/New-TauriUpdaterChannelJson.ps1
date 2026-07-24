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

    [string]$OutputPath,

    [string]$Notes = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

if ($ReleaseTag -cne "app-v$Version") {
    throw 'Release tag must equal app-v<version> exactly before updater metadata is generated.'
}

if (-not (Test-Path -LiteralPath $BundleRoot -PathType Container)) {
    throw "Bundle root not found: $BundleRoot"
}
if (-not $OutputPath) {
    $OutputPath = Join-Path $BundleRoot ("latest-{0}.json" -f $Channel)
}

$nsisRoot = Join-Path $BundleRoot 'nsis'
if (-not (Test-Path -LiteralPath $nsisRoot -PathType Container)) {
    throw "NSIS bundle folder not found: $nsisRoot"
}
$installer = Get-ChildItem -LiteralPath $nsisRoot -Filter '*.exe' -File |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
if (-not $installer) {
    throw "No NSIS installer .exe found under $nsisRoot"
}
$signaturePath = "$($installer.FullName).sig"
if (-not (Test-Path -LiteralPath $signaturePath -PathType Leaf)) {
    throw "Updater signature not found: $signaturePath"
}

$signature = (Get-Content -LiteralPath $signaturePath -Raw).Trim()
if (-not $signature) {
    throw "Updater signature file was empty: $signaturePath"
}
$assetUrl = "https://github.com/$Repository/releases/download/$ReleaseTag/$($installer.Name)"
$payload = [ordered]@{
    version = $Version
    notes = $Notes
    pub_date = (Get-Date).ToUniversalTime().ToString('o')
    platforms = [ordered]@{
        'windows-x86_64' = [ordered]@{
            signature = $signature
            url = $assetUrl
        }
    }
}
$payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding UTF8

$checksumPath = Join-Path $BundleRoot 'SHA256SUMS.txt'
foreach ($path in @($installer.FullName, $signaturePath, $OutputPath)) {
    $hash = Get-FileHash -LiteralPath $path -Algorithm SHA256
    "{0}  {1}" -f $hash.Hash.ToLowerInvariant(), (Split-Path -Leaf $path) |
        Add-Content -LiteralPath $checksumPath -Encoding UTF8
}

Write-Host "Updater channel JSON: $OutputPath"
Write-Host "Installer asset URL : $assetUrl"
Write-Host "Checksums           : $checksumPath"
