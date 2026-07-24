[CmdletBinding()]
param(
    [ValidateSet('beta', 'stable')]
    [string]$Channel = 'beta',

    [string]$Repository = $env:GITHUB_REPOSITORY,

    [string]$UpdaterPublicKey = $env:TAURI_UPDATER_PUBLIC_KEY,

    [string]$Version = $env:MEDIAPIPELINE_SEMVER_VERSION,

    [string]$WindowsCertificateThumbprint = $env:WINDOWS_CERTIFICATE_THUMBPRINT,

    [Parameter(Mandatory)]
    [string]$ResourceRoot,

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

$resourceRootFull = [System.IO.Path]::GetFullPath($ResourceRoot).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
)
$repoWithSeparator = $repoRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
if (
    $resourceRootFull.Equals($repoRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    $resourceRootFull.StartsWith($repoWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)
) {
    throw 'ResourceRoot must be an external sanitized release tree, not the repository or one of its descendants.'
}
if (-not (Test-Path -LiteralPath $resourceRootFull -PathType Container)) {
    throw "ResourceRoot does not exist: $resourceRootFull"
}

$requiredResources = @(
    'release_manifest.json',
    'pyproject.toml',
    'apps\desktop\webview\static\index.html',
    'apps\desktop\runtime\Python\python.exe',
    'src\mediapipeline\desktop\local_api_main.py',
    'ops\pipeline\entrypoints\MediaPipeline.ps1',
    'ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe',
    'ops\pipeline\tools\ffmpeg\bin\ffmpeg.exe',
    'ops\pipeline\tools\ffmpeg\bin\ffprobe.exe',
    'ops\pipeline\tools\MKVToolNix\mkvmerge.exe',
    'ops\pipeline\tools\PgsToSrt\PgsToSrt.exe'
)
foreach ($relativePath in $requiredResources) {
    $requiredPath = Join-Path $resourceRootFull $relativePath
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "ResourceRoot is missing required installer payload: $relativePath"
    }
}

$forbiddenResources = @(
    'LocalBase',
    'RunLogs',
    'apps\desktop\runlogs',
    'ops\pipeline\config\MediaPipeline_config.psd1',
    'ops\pipeline\config\MediaPipeline_config_chatgpt.psd1'
)
foreach ($relativePath in $forbiddenResources) {
    if (Test-Path -LiteralPath (Join-Path $resourceRootFull $relativePath)) {
        throw "ResourceRoot contains forbidden mutable or personal payload: $relativePath"
    }
}

try {
    $releaseManifest = Get-Content -LiteralPath (Join-Path $resourceRootFull 'release_manifest.json') -Raw |
        ConvertFrom-Json -Depth 100
} catch {
    throw "ResourceRoot release_manifest.json is not valid JSON: $($_.Exception.Message)"
}
if ([string]$releaseManifest.schema_version -ne 'mediapipeline_release_manifest.v1') {
    throw 'ResourceRoot release_manifest.json must use mediapipeline_release_manifest.v1.'
}
$manifestPaths = @($releaseManifest.integrity.files | ForEach-Object {
    ([string]$_.path).Replace('/', '\').TrimStart('\')
})
foreach ($relativePath in $requiredResources | Where-Object { $_ -ne 'release_manifest.json' }) {
    if ($manifestPaths -notcontains $relativePath) {
        throw "ResourceRoot manifest does not cover required installer payload: $relativePath"
    }
}

$config = Get-Content -LiteralPath $baseConfigPath -Raw | ConvertFrom-Json -Depth 100
$config.version = $Version
$config.bundle.targets = @('nsis')
$config.bundle | Add-Member -NotePropertyName createUpdaterArtifacts -NotePropertyValue $true -Force
$resourceMap = [ordered]@{}
$resourceMap[(Join-Path $resourceRootFull 'release_manifest.json')] = 'release_manifest.json'
$resourceMap[(Join-Path $resourceRootFull 'pyproject.toml')] = 'pyproject.toml'
$resourceDirectories = [ordered]@{
    'apps\desktop\webview' = 'apps/desktop/webview/'
    'apps\desktop\runtime' = 'apps/desktop/runtime/'
    'src\mediapipeline' = 'src/mediapipeline/'
    'ops\pipeline' = 'ops/pipeline/'
    'ops\scripts' = 'ops/scripts/'
    'ops\release\metadata' = 'ops/release/metadata/'
}
foreach ($entry in $resourceDirectories.GetEnumerator()) {
    $sourceDirectory = (Join-Path $resourceRootFull $entry.Key).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    if (-not (Test-Path -LiteralPath $sourceDirectory -PathType Container)) {
        throw "ResourceRoot is missing required installer directory: $($entry.Key)"
    }
    $resourceMap[$sourceDirectory] = $entry.Value
}
$config.bundle | Add-Member -NotePropertyName resources -NotePropertyValue $resourceMap -Force
if ($WindowsCertificateThumbprint) {
    $config.bundle.windows | Add-Member -NotePropertyName certificateThumbprint -NotePropertyValue $WindowsCertificateThumbprint -Force
}

$endpoint = "https://github.com/$Repository/releases/download/updater-$Channel/latest-$Channel.json"
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
