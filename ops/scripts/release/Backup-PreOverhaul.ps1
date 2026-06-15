<#
.SYNOPSIS
    Produces a complete pre-overhaul backup bundle at an external destination.

.DESCRIPTION
    Phase 0 of docs\architecture\ARCHITECTURAL_OVERHAUL_PLAN.md calls for three artifacts to
    be stored externally as a rollback anchor:

      1. A source archive of tag `v6-pre-overhaul`.
      2. A release-package build copied next to the archive.
      3. A point-in-time snapshot of LocalBase\State.

    This script produces all three under a single -Destination directory
    and writes a manifest with SHA-256 evidence for every file.

    The script is idempotent in the sense that it refuses to overwrite a
    non-empty destination. To replace a previous backup, delete the
    destination directory first.

    It is operator-run only. Nothing in CI calls it. Nothing in the build
    pipeline calls it. Nothing here mutates the repo.

.PARAMETER Destination
    External directory to write the backup into. Must NOT exist or must
    be empty. Required. No default is provided so an absent argument
    cannot accidentally land in $env:USERPROFILE.

.PARAMETER Tag
    Git tag to archive. Defaults to 'v6-pre-overhaul'.

.PARAMETER SkipReleaseBuild
    Skip step 2 (release build). Use when the release build was just
    produced and you only want the source archive + state snapshot.

.PARAMETER SkipStateSnapshot
    Skip step 3 (LocalBase\State copy). Use when state has already been
    archived elsewhere.

.PARAMETER DryRun
    Print what would happen. Do not write anything.

.EXAMPLE
    .\ops\scripts\release\Backup-PreOverhaul.ps1 -Destination 'D:\Backups\MediaPipeline\v6-pre-overhaul-2026-05-28'

.EXAMPLE
    .\ops\scripts\release\Backup-PreOverhaul.ps1 -Destination 'E:\Archive\mpv6' -SkipReleaseBuild -DryRun
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Destination,

    [string]$Tag = 'v6-pre-overhaul',

    [switch]$SkipReleaseBuild,

    [switch]$SkipStateSnapshot,

    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Write-Step {
    param([string]$Message)
    Write-Host ("[backup] {0}" -f $Message)
}

function Assert-Tool {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required tool not on PATH: $Name"
    }
}

function Get-FileSha256Hex {
    param([string]$Path)
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

# --- Pre-flight checks ------------------------------------------------------

Assert-Tool -Name 'git'

$RepoRoot = (git rev-parse --show-toplevel) 2>$null
if (-not $RepoRoot) { throw "Not inside a git repository. Run from the project root." }
$RepoRoot = $RepoRoot.Trim()
$Destination = [System.IO.Path]::GetFullPath($Destination)

Write-Step "Repo root: $RepoRoot"

$tagSha = (git rev-list -n 1 $Tag) 2>$null
if (-not $tagSha) { throw "Tag '$Tag' not found. Use 'git tag' to list available tags." }
Write-Step "Tag '$Tag' resolves to commit $tagSha"

# Destination must not exist, or must be empty.
if (Test-Path -LiteralPath $Destination) {
    $existing = @(Get-ChildItem -LiteralPath $Destination -Force -ErrorAction SilentlyContinue)
    if ($existing.Count -gt 0) {
        throw "Destination '$Destination' exists and is not empty. Delete it first or choose another path."
    }
    Write-Step "Destination exists and is empty: $Destination"
} else {
    if ($DryRun) {
        Write-Step "[dry-run] Would create destination: $Destination"
    } else {
        [System.IO.Directory]::CreateDirectory($Destination) | Out-Null
        Write-Step "Created destination: $Destination"
    }
}

# Resolve paths used downstream.
$SourceArchivePath = Join-Path $Destination ("source-{0}.zip" -f $Tag)
$ReleaseDir        = Join-Path $Destination 'release'
$StateDir          = Join-Path $Destination 'state-snapshot'
$ManifestPath      = Join-Path $Destination 'manifest.json'

# --- Step 1: source archive ------------------------------------------------

Write-Step "Step 1: source archive of tag '$Tag'"
if ($DryRun) {
    Write-Step "[dry-run] Would run: git archive --format=zip $Tag -o $SourceArchivePath"
} else {
    Push-Location -LiteralPath $RepoRoot
    try {
        git archive --format=zip --output=$SourceArchivePath $Tag
        if ($LASTEXITCODE -ne 0) { throw "git archive failed with exit code $LASTEXITCODE" }
    } finally {
        Pop-Location
    }
    $size = (Get-Item -LiteralPath $SourceArchivePath).Length
    Write-Step "Wrote $SourceArchivePath ($('{0:N0}' -f $size) bytes)"
}

# --- Step 2: release build copy --------------------------------------------

if ($SkipReleaseBuild) {
    Write-Step "Step 2: skipped (--SkipReleaseBuild)"
} else {
    Write-Step "Step 2: invoking ops/scripts/release/build.ps1 -> $ReleaseDir"
    $buildScript = Join-Path $RepoRoot 'ops\scripts\release\build.ps1'
    if (-not (Test-Path -LiteralPath $buildScript)) {
        throw "Release build script not found at ops\scripts\release\build.ps1."
    }
    if ($DryRun) {
        Write-Step "[dry-run] Would run: & '$buildScript' -DestinationRoot '$ReleaseDir' -Verify -Zip"
    } else {
        & $buildScript -DestinationRoot $ReleaseDir -Verify -Zip
        if ($LASTEXITCODE -ne 0) { throw "Release build failed with exit code $LASTEXITCODE" }
    }
}

# --- Step 3: LocalBase\State snapshot --------------------------------------

if ($SkipStateSnapshot) {
    Write-Step "Step 3: skipped (--SkipStateSnapshot)"
} else {
    $stateSource = Join-Path $RepoRoot 'LocalBase\State'
    if (-not (Test-Path -LiteralPath $stateSource)) {
        Write-Step "Step 3: LocalBase\State not present (no runtime state to snapshot)"
    } else {
        Write-Step "Step 3: copying LocalBase\State -> $StateDir"
        if ($DryRun) {
            $count = (Get-ChildItem -LiteralPath $stateSource -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object).Count
            Write-Step "[dry-run] Would copy approximately $count files"
        } else {
            [System.IO.Directory]::CreateDirectory($StateDir) | Out-Null
            Get-ChildItem -LiteralPath $stateSource -Force | ForEach-Object {
                Copy-Item -LiteralPath $_.FullName -Destination $StateDir -Recurse -Force
            }
        }
    }
}

# --- Step 4: manifest -------------------------------------------------------

if ($DryRun) {
    Write-Step "[dry-run] Would write manifest at $ManifestPath"
    return
}

Write-Step "Step 4: writing manifest"

$manifestEntries = @()
Get-ChildItem -LiteralPath $Destination -Recurse -File | ForEach-Object {
    $relPath = $_.FullName.Substring($Destination.Length).TrimStart('\','/')
    if ($relPath -ieq 'manifest.json') { return }
    $hash = Get-FileSha256Hex -Path $_.FullName
    $manifestEntries += [pscustomobject]@{
        path        = $relPath -replace '\\', '/'
        size_bytes  = $_.Length
        sha256      = $hash
    }
}

$manifest = [ordered]@{
    schema_version    = 1
    created_at_utc    = (Get-Date).ToUniversalTime().ToString('o')
    repo_root         = '<repo-root>'
    tag               = $Tag
    tag_sha           = $tagSha
    skipped_steps     = @(
        if ($SkipReleaseBuild)  { 'release-build' }
        if ($SkipStateSnapshot) { 'state-snapshot' }
    )
    file_count        = $manifestEntries.Count
    total_size_bytes  = ($manifestEntries | Measure-Object -Property size_bytes -Sum).Sum
    files             = $manifestEntries
}

$manifestJson = $manifest | ConvertTo-Json -Depth 6
Set-Content -LiteralPath $ManifestPath -Value $manifestJson -Encoding UTF8
Write-Step "Wrote manifest with $($manifest.file_count) files, $('{0:N0}' -f $manifest.total_size_bytes) bytes"

# --- Step 5: read-back verification ----------------------------------------

Write-Step "Step 5: verifying manifest hashes"
$mismatch = 0
foreach ($entry in $manifestEntries) {
    $abs = Join-Path $Destination ($entry.path -replace '/', '\')
    $actual = Get-FileSha256Hex -Path $abs
    if ($actual -ne $entry.sha256) {
        Write-Warning "SHA mismatch: $($entry.path)"
        $mismatch++
    }
}
if ($mismatch -gt 0) {
    throw "Backup verification FAILED: $mismatch file(s) mismatched."
}
Write-Step "All hashes verified. Backup complete: $Destination"
