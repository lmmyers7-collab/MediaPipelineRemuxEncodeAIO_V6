[CmdletBinding()]
param(
    [ValidateSet('beta', 'stable')]
    [string]$Channel = 'beta',

    [string]$Repository = $env:GITHUB_REPOSITORY,

    [string]$UpdaterPublicKey = $env:TAURI_UPDATER_PUBLIC_KEY,

    [string]$Version = $env:MEDIAPIPELINE_SEMVER_VERSION,

    [string]$WindowsCertificateThumbprint = $env:WINDOWS_CERTIFICATE_THUMBPRINT,

    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptRoot))))
$baseConfigPath = Join-Path $repoRoot 'apps\desktop\tauri\src-tauri\tauri.conf.json'
if (-not (Test-Path -LiteralPath $baseConfigPath -PathType Leaf)) {
    throw "Tauri config not found: $baseConfigPath"
}
if (-not $Repository) {
    throw 'Repository is required. Set GITHUB_REPOSITORY or pass -Repository owner/repo.'
}
if (-not $UpdaterPublicKey) {
    throw 'Updater public key is required. Set TAURI_UPDATER_PUBLIC_KEY from the matching private updater signing key.'
}
if (-not $Version) {
    $Version = '2026.6.4+001'
}
if (-not $OutputPath) {
    $OutputPath = Join-Path $repoRoot ("apps\desktop\tauri\src-tauri\tauri.{0}.generated.conf.json" -f $Channel)
}

$config = Get-Content -LiteralPath $baseConfigPath -Raw | ConvertFrom-Json -Depth 100
$config.version = $Version
$config.bundle.targets = @('nsis')
$config.bundle | Add-Member -NotePropertyName createUpdaterArtifacts -NotePropertyValue $true -Force
if ($WindowsCertificateThumbprint) {
    $config.bundle.windows | Add-Member -NotePropertyName certificateThumbprint -NotePropertyValue $WindowsCertificateThumbprint -Force
}

$endpoint = "https://github.com/$Repository/releases/latest/download/latest-$Channel.json"
$updater = [pscustomobject][ordered]@{
    pubkey = $UpdaterPublicKey
    endpoints = @($endpoint)
    windows = [pscustomobject][ordered]@{
        installMode = 'passive'
    }
}
$config | Add-Member -NotePropertyName plugins -NotePropertyValue ([pscustomobject]@{}) -Force
$config.plugins | Add-Member -NotePropertyName updater -NotePropertyValue $updater -Force

$parent = Split-Path -Parent $OutputPath
if ($parent -and -not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}
$config | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Host "Generated Tauri productization config: $OutputPath"
Write-Host "Updater endpoint: $endpoint"
