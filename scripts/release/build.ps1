[CmdletBinding()]
param(
    [string]$DestinationRoot,
    [switch]$Force,
    [switch]$Zip,
    [switch]$IncludeTests,
    [switch]$IncludeDevDocs,
    [switch]$IncludeOptionalTools,
    [switch]$IncludeToolDocs,
    [switch]$IncludeTauriPreviewBinary,
    [switch]$KeepPersonalConfig,
    [switch]$Verify,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Get-RelativePathText {
    param(
        [Parameter(Mandatory)][string]$BasePath,
        [Parameter(Mandatory)][string]$FullPath
    )
    $baseUri = [System.Uri]::new((Join-Path ([System.IO.Path]::GetFullPath($BasePath)) '.'))
    $fullUri = [System.Uri]::new([System.IO.Path]::GetFullPath($FullPath))
    return [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($fullUri).ToString()).Replace('/', '\')
}

function Get-DeployExclusionReason {
    param([Parameter(Mandatory)][string]$RelativePath)

    return Get-MediaPipelineReleaseExclusionReason `
        -RelativePath $RelativePath `
        -IncludeTests:$([bool]$IncludeTests) `
        -IncludeDevDocs:$([bool]$IncludeDevDocs) `
        -IncludeOptionalTools:$([bool]$IncludeOptionalTools) `
        -IncludeToolDocs:$([bool]$IncludeToolDocs) `
        -KeepPersonalConfig:$([bool]$KeepPersonalConfig)
}

function Get-FileVersionText {
    param([Parameter(Mandatory)][string]$RelativePath)
    $path = Join-Path $script:SourceRoot $RelativePath
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    $item = Get-Item -LiteralPath $path
    $version = $item.VersionInfo.ProductVersion
    if (-not $version) { $version = $item.VersionInfo.FileVersion }
    return [ordered]@{
        path = $RelativePath
        version = $version
        bytes = $item.Length
    }
}

function Get-PythonPackageVersions {
    $python = Join-Path $script:SourceRoot 'DesktopApp\Runtime\Python\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { return @{} }
    $code = @'
import json
import importlib.metadata as md
names = ["psutil", "pysubs2", "packaging", "darkdetect"]
out = {}
for name in names:
    try:
        out[name] = md.version(name)
    except md.PackageNotFoundError:
        out[name] = None
print(json.dumps(out, sort_keys=True))
'@
    try {
        $json = & $python -c $code 2>$null
        if ($LASTEXITCODE -eq 0 -and $json) {
            return ($json | ConvertFrom-Json -AsHashtable)
        }
    } catch { }
    return @{}
}

function Resolve-ReleaseVerificationPowerShell {
    param([Parameter(Mandatory)][string]$ReleaseRoot)

    $bundled = Join-Path $ReleaseRoot 'Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe'
    if (Test-Path -LiteralPath $bundled -PathType Leaf) {
        return (Resolve-Path -LiteralPath $bundled).Path
    }

    $cmd = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    return $null
}

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$script:SourceRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent $scriptRoot)))
$releasePolicyModule = Join-Path $script:SourceRoot 'scripts\release\release_policy.ps1'
if (-not (Test-Path -LiteralPath $releasePolicyModule -PathType Leaf)) {
    throw "Release policy module is missing: $releasePolicyModule"
}
. $releasePolicyModule
if (-not $DestinationRoot) {
    $DestinationRoot = Join-Path (Split-Path -Parent $script:SourceRoot) ("MediaPipelineRemuxEncodeAIO_V6_Deployable_{0}" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
}
$destinationFull = [System.IO.Path]::GetFullPath($DestinationRoot)

if ($destinationFull.TrimEnd('\') -eq $script:SourceRoot.TrimEnd('\') -or $destinationFull.StartsWith($script:SourceRoot.TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Destination must not be the source folder or a child of it: $destinationFull"
}

$allFiles = @(Get-ChildItem -LiteralPath $script:SourceRoot -Recurse -File -Force)
$copyPlan = [System.Collections.Generic.List[object]]::new()
$excludePlan = [System.Collections.Generic.List[object]]::new()

foreach ($file in $allFiles) {
    $relative = Get-RelativePathText -BasePath $script:SourceRoot -FullPath $file.FullName
    $reason = Get-DeployExclusionReason -RelativePath $relative
    if ($reason) {
        $excludePlan.Add([pscustomobject]@{ path = $relative; reason = $reason; bytes = $file.Length })
        continue
    }
    $copyPlan.Add([pscustomobject]@{
        source = $file.FullName
        relative = $relative
        destination = Join-Path $destinationFull $relative
        bytes = $file.Length
    })
}

$tauriPreviewBinary = $null
if ($IncludeTauriPreviewBinary) {
    $tauriPreviewBinary = Join-Path $script:SourceRoot 'DesktopApp\tauri_shell\src-tauri\target\release\mediapipeline-tauri-shell.exe'
    if (-not (Test-Path -LiteralPath $tauriPreviewBinary -PathType Leaf)) {
        throw "IncludeTauriPreviewBinary was requested, but the compiled Tauri executable was not found: $tauriPreviewBinary. Run the Tauri release build first."
    }
    $tauriBinaryItem = Get-Item -LiteralPath $tauriPreviewBinary
    $tauriBinaryRelative = 'DesktopApp\tauri_shell\mediapipeline-tauri-shell.exe'
    $alreadyPlanned = @($copyPlan | Where-Object { $_.relative -eq $tauriBinaryRelative }).Count -gt 0
    if (-not $alreadyPlanned) {
        $copyPlan.Add([pscustomobject]@{
            source = $tauriBinaryItem.FullName
            relative = $tauriBinaryRelative
            destination = Join-Path $destinationFull $tauriBinaryRelative
            bytes = $tauriBinaryItem.Length
        })
    }
}

$summary = [ordered]@{
    source_root = $script:SourceRoot
    destination_root = $destinationFull
    generated_at = (Get-Date).ToString('o')
    personal_config_included = [bool]$KeepPersonalConfig
    tests_included = [bool]$IncludeTests
    dev_docs_included = [bool]$IncludeDevDocs
    optional_tools_included = [bool]$IncludeOptionalTools
    tool_docs_included = [bool]$IncludeToolDocs
    tauri_preview_binary_included = [bool]$IncludeTauriPreviewBinary
    zip_requested = [bool]$Zip
    verify_requested = [bool]$Verify
    copied_file_count = $copyPlan.Count
    excluded_file_count = $excludePlan.Count
    copied_bytes = [int64](($copyPlan | Measure-Object -Property bytes -Sum).Sum)
    excluded_bytes = [int64](($excludePlan | Measure-Object -Property bytes -Sum).Sum)
}

Write-Host "Source      : $($summary.source_root)"
Write-Host "Destination : $($summary.destination_root)"
Write-Host "Mode        : $(if ($KeepPersonalConfig) { 'personal mirror' } else { 'new-user deployable; live config stripped' })"
Write-Host "Copy files  : $($summary.copied_file_count)"
Write-Host "Exclude     : $($summary.excluded_file_count)"

if ($DryRun) {
    Write-Host ''
    Write-Host 'Dry run only. No files copied.'
    if ($Verify) {
        Write-Host 'Verify     : skipped during dry run because no release folder was copied.'
    }
    $excludePlan |
        Group-Object reason |
        Sort-Object Name |
        ForEach-Object { Write-Host ("Excluded {0,4} file(s): {1}" -f $_.Count, $_.Name) }
    return
}

if (Test-Path -LiteralPath $destinationFull) {
    $resolvedDestination = (Resolve-Path -LiteralPath $destinationFull).Path
    if (-not $Force) {
        throw "Destination already exists. Use -Force to replace it: $resolvedDestination"
    }
    if ($resolvedDestination.TrimEnd('\') -eq $script:SourceRoot.TrimEnd('\') -or $resolvedDestination.StartsWith($script:SourceRoot.TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove unsafe destination: $resolvedDestination"
    }
    Remove-Item -LiteralPath $resolvedDestination -Recurse -Force
}

New-Item -ItemType Directory -Path $destinationFull -Force | Out-Null
foreach ($entry in $copyPlan) {
    $parent = Split-Path -Parent $entry.destination
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Copy-Item -LiteralPath $entry.source -Destination $entry.destination -Force
}

$manifest = [ordered]@{
    schema_version = 'mediapipeline_release_manifest.v1'
    summary = $summary
    config_policy = if ($KeepPersonalConfig) {
        'Pipeline\MediaPipeline_config.psd1 (and legacy Pipeline\MediaPipeline_config_chatgpt.psd1) were copied as-is.'
    } else {
        'Pipeline\MediaPipeline_config.psd1 and legacy Pipeline\MediaPipeline_config_chatgpt.psd1 were excluded. New users should run setup; Pipeline\MediaPipeline_config_template.psd1 is included for reference.'
    }
    tool_policy = if ($IncludeOptionalTools) {
        'Optional bundled tool binaries and GUI assets were included.'
    } else {
        'Only runtime-required bundled command tools were included. Use -IncludeOptionalTools to keep ffplay and unused MKVToolNix GUI/diagnostic utilities.'
    }
    tool_docs_policy = if ($IncludeToolDocs) {
        'Bundled tool documentation/examples were included.'
    } else {
        'Bundled MKVToolNix documentation/examples were excluded. Use -IncludeToolDocs to keep them.'
    }
    release_policy = Get-MediaPipelineReleasePolicyManifest `
        -IncludeTests:$([bool]$IncludeTests) `
        -IncludeDevDocs:$([bool]$IncludeDevDocs) `
        -IncludeOptionalTools:$([bool]$IncludeOptionalTools) `
        -IncludeToolDocs:$([bool]$IncludeToolDocs) `
        -IncludeTauriPreviewBinary:$([bool]$IncludeTauriPreviewBinary) `
        -KeepPersonalConfig:$([bool]$KeepPersonalConfig)
    tauri_preview_binary_policy = if ($IncludeTauriPreviewBinary) {
        'Compiled Tauri preview executable was copied to DesktopApp\tauri_shell\mediapipeline-tauri-shell.exe for package-mode launch validation.'
    } else {
        'Compiled Tauri preview executable was not included. Build with -IncludeTauriPreviewBinary after a Tauri release build to prepare PG-3 package-mode validation.'
    }
    bundled_tools = [ordered]@{
        powershell = Get-FileVersionText 'Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe'
        ffmpeg = Get-FileVersionText 'Pipeline\Tools\ffmpeg\bin\ffmpeg.exe'
        ffprobe = Get-FileVersionText 'Pipeline\Tools\ffmpeg\bin\ffprobe.exe'
        mkvmerge = Get-FileVersionText 'Pipeline\Tools\MKVToolNix\mkvmerge.exe'
        pgs_to_srt = Get-FileVersionText 'Pipeline\Tools\PgsToSrt\PgsToSrt.exe'
    }
    python_packages = Get-PythonPackageVersions
    excluded_files = @($excludePlan | Sort-Object path)
}

$manifestPath = Join-Path $destinationFull 'release_manifest.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Host "Manifest    : $manifestPath"

if ($Verify) {
    $releaseVerifier = Join-Path $destinationFull 'scripts\release\test.ps1'
    if (-not (Test-Path -LiteralPath $releaseVerifier -PathType Leaf)) {
        throw "Release verifier was not copied into the package: $releaseVerifier"
    }

    $verifyPwsh = Resolve-ReleaseVerificationPowerShell -ReleaseRoot $destinationFull
    if (-not $verifyPwsh) {
        throw 'Cannot run release verification because pwsh was not found in the release or on PATH.'
    }

    $verifyArgs = [System.Collections.Generic.List[string]]::new()
    $verifyArgs.AddRange([string[]]@(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $releaseVerifier,
        '-BundleRoot', $destinationFull
    ))
    if ($IncludeTests) {
        $verifyArgs.Add('-RequireTests')
    }

    Write-Host "Verify      : $releaseVerifier"
    & $verifyPwsh @($verifyArgs.ToArray())
    if ($LASTEXITCODE -ne 0) {
        throw "Release verification failed with exit $LASTEXITCODE."
    }
}

if ($Zip) {
    $zipPath = $destinationFull.TrimEnd('\') + '.zip'
    if (Test-Path -LiteralPath $zipPath) {
        if (-not $Force) { throw "Zip already exists. Use -Force to replace it: $zipPath" }
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $destinationFull '*') -DestinationPath $zipPath -Force
    Write-Host "Zip         : $zipPath"
}

Write-Host 'Release build complete.'
