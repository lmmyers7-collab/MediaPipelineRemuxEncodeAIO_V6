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
    [switch]$AllowTestlessVerify,
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

function ConvertTo-ReleaseRelativeDirectory {
    param([Parameter(Mandatory)][string]$RelativePath)

    return $RelativePath.Replace('/', '\').Trim('\')
}

function Test-ReleaseTraversalDirectoryPruned {
    param([Parameter(Mandatory)][string]$RelativePath)

    $relative = ConvertTo-ReleaseRelativeDirectory -RelativePath $RelativePath
    if (-not $relative) { return $false }

    foreach ($excludedRoot in @(
        '.git',
        '.github',
        '.codex',
        '.codex-plugin',
        '.mypy_cache',
        '.pytest_cache',
        '__pycache__',
        'CodexVerification',
        'LocalBase',
        'RunLogs',
        'node_modules',
        'apps\desktop\runlogs',
        'apps\desktop\tauri\node_modules',
        'apps\desktop\tauri\src-tauri\gen',
        'apps\desktop\tauri\src-tauri\target',
        'docs\PG3CleanMachineReports',
        'docs\reviews',
        'ops\pipeline\config\backups'
    )) {
        if (
            $relative.Equals($excludedRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
            $relative.StartsWith($excludedRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)
        ) {
            return $true
        }
    }

    return $false
}

function Get-ReleaseSourceFileItems {
    param([Parameter(Mandatory)][string]$Root)

    $queue = [System.Collections.Generic.Queue[System.IO.DirectoryInfo]]::new()
    $queue.Enqueue((Get-Item -LiteralPath $Root))
    while ($queue.Count -gt 0) {
        $directory = $queue.Dequeue()
        foreach ($file in @(Get-ChildItem -LiteralPath $directory.FullName -File -Force -ErrorAction SilentlyContinue)) {
            $file
        }
        foreach ($childDirectory in @(Get-ChildItem -LiteralPath $directory.FullName -Directory -Force -ErrorAction SilentlyContinue)) {
            $relative = Get-RelativePathText -BasePath $Root -FullPath $childDirectory.FullName
            if (Test-ReleaseTraversalDirectoryPruned -RelativePath $relative) {
                continue
            }
            $queue.Enqueue($childDirectory)
        }
    }
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
    $python = Join-Path $script:SourceRoot 'apps\desktop\runtime\Python\python.exe'
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

    $bundled = Join-Path $ReleaseRoot 'ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe'
    if (Test-Path -LiteralPath $bundled -PathType Leaf) {
        return (Resolve-Path -LiteralPath $bundled).Path
    }

    $cmd = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    return $null
}

function ConvertTo-ReleaseCanonicalPath {
    param([Parameter(Mandatory)][string]$Path)

    $full = [System.IO.Path]::GetFullPath($Path)
    $root = [System.IO.Path]::GetPathRoot($full)
    $trimmed = $full.TrimEnd([char[]]@('\', '/'))
    if ($root) {
        $rootTrimmed = $root.TrimEnd([char[]]@('\', '/'))
        if ($trimmed.Equals($rootTrimmed, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $root
        }
    }
    return $trimmed
}

function Test-ReleasePathEqualOrChild {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Root
    )

    $pathCanonical = ConvertTo-ReleaseCanonicalPath -Path $Path
    $rootCanonical = ConvertTo-ReleaseCanonicalPath -Path $Root
    if ($pathCanonical.Equals($rootCanonical, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }
    $prefix = $rootCanonical
    if (-not ($prefix.EndsWith('\') -or $prefix.EndsWith('/'))) {
        $prefix += [System.IO.Path]::DirectorySeparatorChar
    }
    return $pathCanonical.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-ReleaseDirectoryIsEmpty {
    param([Parameter(Mandatory)][string]$Path)

    $children = @(Get-ChildItem -LiteralPath $Path -Force -ErrorAction SilentlyContinue | Select-Object -First 1)
    return $children.Count -eq 0
}

function Test-ReleaseDestinationHasMarker {
    param([Parameter(Mandatory)][string]$Path)

    $manifestPath = Join-Path $Path 'release_manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        return $false
    }
    try {
        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    } catch {
        return $false
    }
    return [string]$manifest.schema_version -eq 'mediapipeline_release_manifest.v1'
}

function Test-ReleaseDestinationHasInProgressMarker {
    param([Parameter(Mandatory)][string]$Path)

    $markerPath = Join-Path $Path '.release_in_progress.json'
    if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
        return $false
    }
    try {
        $marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
    } catch {
        return $false
    }
    return [string]$marker.schema_version -eq 'mediapipeline_release_in_progress.v1'
}

function Assert-ReleaseDestinationPathAllowed {
    param(
        [Parameter(Mandatory)][string]$DestinationPath,
        [Parameter(Mandatory)][string]$SourceRoot
    )

    $destinationCanonical = ConvertTo-ReleaseCanonicalPath -Path $DestinationPath
    $sourceCanonical = ConvertTo-ReleaseCanonicalPath -Path $SourceRoot
    $destinationRoot = [System.IO.Path]::GetPathRoot($destinationCanonical)
    if ($destinationRoot -and $destinationCanonical.Equals($destinationRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Destination must not be a filesystem root: $destinationCanonical"
    }

    $profileRoots = [System.Collections.Generic.List[string]]::new()
    foreach ($candidate in @(
        $env:USERPROFILE,
        $env:HOME,
        [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
    )) {
        if ($candidate) {
            [void]$profileRoots.Add((ConvertTo-ReleaseCanonicalPath -Path $candidate))
        }
    }
    foreach ($profileRoot in @($profileRoots.ToArray() | Select-Object -Unique)) {
        if ($destinationCanonical.Equals($profileRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Destination must not be the user profile root: $destinationCanonical"
        }
    }

    if (Test-ReleasePathEqualOrChild -Path $destinationCanonical -Root $sourceCanonical) {
        throw "Destination must not be the source folder or a child of it: $destinationCanonical"
    }
    if (Test-ReleasePathEqualOrChild -Path $sourceCanonical -Root $destinationCanonical) {
        throw "Destination must not be an ancestor of the source folder: $destinationCanonical"
    }
    return $destinationCanonical
}

function Assert-ReleaseDestinationReplacementAllowed {
    param(
        [Parameter(Mandatory)][string]$DestinationPath,
        [Parameter(Mandatory)][string]$SourceRoot
    )

    $resolvedDestination = (Resolve-Path -LiteralPath $DestinationPath).Path
    $destinationCanonical = Assert-ReleaseDestinationPathAllowed -DestinationPath $resolvedDestination -SourceRoot $SourceRoot
    if (-not (Test-Path -LiteralPath $destinationCanonical -PathType Container)) {
        throw "Destination exists but is not a directory: $destinationCanonical"
    }
    if (Test-ReleaseDirectoryIsEmpty -Path $destinationCanonical) {
        return $destinationCanonical
    }
    if (Test-ReleaseDestinationHasMarker -Path $destinationCanonical) {
        return $destinationCanonical
    }
    if (Test-ReleaseDestinationHasInProgressMarker -Path $destinationCanonical) {
        return $destinationCanonical
    }
    throw "Refusing to replace destination without a MediaPipeline release manifest marker: $destinationCanonical"
}

function Get-MediaPipelineReleaseLabel {
    $versionFile = Join-Path $script:SourceRoot 'ops\release\metadata\VERSION'
    if (Test-Path -LiteralPath $versionFile -PathType Leaf) {
        $label = (Get-Content -LiteralPath $versionFile -Raw).Trim()
        if ($label) { return $label }
    }
    return 'local'
}

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$script:SourceRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptRoot))))
$releasePolicyModule = Join-Path $script:SourceRoot 'ops\scripts\release\release_policy.ps1'
if (-not (Test-Path -LiteralPath $releasePolicyModule -PathType Leaf)) {
    throw "Release policy module is missing: $releasePolicyModule"
}
. $releasePolicyModule
if ($KeepPersonalConfig -and $Zip) {
    throw 'KeepPersonalConfig cannot be combined with -Zip. Build personal mirrors as directories only, or omit -KeepPersonalConfig for a distributable zip.'
}
if ($Verify -and -not $IncludeTests -and -not $AllowTestlessVerify) {
    throw 'Release verification requires -IncludeTests. Use -AllowTestlessVerify only for local/dev package smoke checks that must not be treated as release acceptance.'
}
if (-not $DestinationRoot) {
    $releaseLabel = Get-MediaPipelineReleaseLabel
    $DestinationRoot = Join-Path (Split-Path -Parent $script:SourceRoot) ("MediaPipelineRemuxEncodeAIO_{0}_Portable_{1}" -f $releaseLabel, (Get-Date -Format 'yyyyMMdd_HHmmss'))
}
$destinationFull = Assert-ReleaseDestinationPathAllowed -DestinationPath $DestinationRoot -SourceRoot $script:SourceRoot

$allFiles = @(Get-ReleaseSourceFileItems -Root $script:SourceRoot)
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
    $tauriPreviewBinary = Join-Path $script:SourceRoot 'apps\desktop\tauri\src-tauri\target\release\mediapipeline-tauri-shell.exe'
    if (-not (Test-Path -LiteralPath $tauriPreviewBinary -PathType Leaf)) {
        throw "IncludeTauriPreviewBinary was requested, but the compiled Tauri executable was not found: $tauriPreviewBinary. Run the Tauri release build first."
    }
    $tauriBinaryItem = Get-Item -LiteralPath $tauriPreviewBinary
    $tauriBinaryRelative = 'apps\desktop\tauri\mediapipeline-tauri-shell.exe'
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
    source_root = '<repo-root>'
    destination_root = '<release-root>'
    generated_at = (Get-Date).ToString('o')
    personal_config_included = [bool]$KeepPersonalConfig
    tests_included = [bool]$IncludeTests
    dev_docs_included = [bool]$IncludeDevDocs
    optional_tools_included = [bool]$IncludeOptionalTools
    tool_docs_included = [bool]$IncludeToolDocs
    tauri_preview_binary_included = [bool]$IncludeTauriPreviewBinary
    zip_requested = [bool]$Zip
    verify_requested = [bool]$Verify
    testless_verify_allowed = [bool]$AllowTestlessVerify
    copied_file_count = $copyPlan.Count
    excluded_file_count = $excludePlan.Count
    copied_bytes = [int64](($copyPlan | Measure-Object -Property bytes -Sum).Sum)
    excluded_bytes = [int64](($excludePlan | Measure-Object -Property bytes -Sum).Sum)
}

Write-Host "Source      : $script:SourceRoot"
Write-Host "Destination : $destinationFull"
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
    if (-not $Force) {
        $resolvedDestination = (Resolve-Path -LiteralPath $destinationFull).Path
        throw "Destination already exists. Use -Force to replace it: $resolvedDestination"
    }
    $resolvedDestination = Assert-ReleaseDestinationReplacementAllowed -DestinationPath $destinationFull -SourceRoot $script:SourceRoot
    Remove-Item -LiteralPath $resolvedDestination -Recurse -Force
}

New-Item -ItemType Directory -Path $destinationFull -Force | Out-Null
$inProgressMarkerPath = Join-Path $destinationFull '.release_in_progress.json'
$inProgressMarker = [ordered]@{
    schema_version = 'mediapipeline_release_in_progress.v1'
    generated_at = (Get-Date).ToString('o')
    source_root = '<repo-root>'
    destination_root = '<release-root>'
    recovery = 'If copying is interrupted before release_manifest.json is written, rerun build.ps1 with -Force to replace this partial release directory.'
}
$inProgressMarker | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $inProgressMarkerPath -Encoding UTF8
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
        'ops\pipeline\config\MediaPipeline_config.psd1 (and legacy ops\pipeline\config\MediaPipeline_config_chatgpt.psd1) were copied as-is.'
    } else {
        'ops\pipeline\config\MediaPipeline_config.psd1 and legacy ops\pipeline\config\MediaPipeline_config_chatgpt.psd1 were excluded. New users should run setup; ops\pipeline\config\MediaPipeline_config_template.psd1 and ops\pipeline\config\profiles\Default.psd1 are included with the packaged custom RenameMovieFilterOptions, RenameMovieFilterTerms, and RenameMovieRemoveTerms deployment baseline.'
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
        'Compiled Tauri preview executable was copied to apps\desktop\tauri\mediapipeline-tauri-shell.exe for package-mode launch validation.'
    } else {
        'Compiled Tauri preview executable was not included. Build with -IncludeTauriPreviewBinary after a Tauri release build to prepare PG-3 package-mode validation.'
    }
    bundled_tools = [ordered]@{
        powershell = Get-FileVersionText 'ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe'
        ffmpeg = Get-FileVersionText 'ops\pipeline\tools\ffmpeg\bin\ffmpeg.exe'
        ffprobe = Get-FileVersionText 'ops\pipeline\tools\ffmpeg\bin\ffprobe.exe'
        mkvmerge = Get-FileVersionText 'ops\pipeline\tools\MKVToolNix\mkvmerge.exe'
        pgs_to_srt = Get-FileVersionText 'ops\pipeline\tools\PgsToSrt\PgsToSrt.exe'
    }
    python_packages = Get-PythonPackageVersions
    excluded_files = @($excludePlan | Sort-Object path)
}

$manifestPath = Join-Path $destinationFull 'release_manifest.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Remove-Item -LiteralPath $inProgressMarkerPath -Force -ErrorAction SilentlyContinue
Write-Host "Manifest    : $manifestPath"

if ($Verify) {
    $releaseVerifier = Join-Path $destinationFull 'ops\scripts\release\test.ps1'
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
    } elseif ($AllowTestlessVerify) {
        Write-Warning 'Release verification is running without tests because -AllowTestlessVerify was supplied. This is not release acceptance.'
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
