param()

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSCommandPath."
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -PathType Container)) {
    throw "Resolved repository root is missing ops\pipeline\engine: $repoRoot"
}
. (Join-Path $repoRoot 'ops\pipeline\engine\queue\file_overrides.ps1')

function Assert-Equal {
    param(
        [Parameter(Mandatory)] $Actual,
        [Parameter(Mandatory)] $Expected,
        [Parameter(Mandatory)] [string] $Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected' but got '$Actual'."
    }
}

function Assert-True {
    param(
        [Parameter(Mandatory)] [bool] $Condition,
        [Parameter(Mandatory)] [string] $Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-ThrowsContains {
    param(
        [Parameter(Mandatory)] [scriptblock] $ScriptBlock,
        [Parameter(Mandatory)] [string] $ExpectedText,
        [Parameter(Mandatory)] [string] $Message
    )
    try {
        & $ScriptBlock | Out-Null
    } catch {
        $actual = [string]$_.Exception.Message
        if ($actual -like "*$ExpectedText*") { return }
        throw "$Message Expected error containing '$ExpectedText' but got '$actual'."
    }
    throw "$Message Expected an error containing '$ExpectedText'."
}

function Write-Log { param($Message, $Level) }

$invalidManifestRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-file-overrides-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $invalidManifestRoot -Force | Out-Null
$invalidManifestPath = Join-Path $invalidManifestRoot 'file_overrides.json'
[System.IO.File]::WriteAllText($invalidManifestPath, '{not-json', [System.Text.Encoding]::UTF8)
$script:LocalStateLayout = [pscustomobject]@{ Paths = [pscustomobject]@{ FileOverrides = $invalidManifestPath } }
$script:CachedFileOverridesManifest = $null
try {
    Assert-ThrowsContains -ScriptBlock { Get-FileOverridesManifest } -ExpectedText 'file_overrides.json is malformed' -Message 'Malformed persisted overrides must fail closed.'
} finally {
    $script:LocalStateLayout = $null
    $script:CachedFileOverridesManifest = $null
    Remove-Item -LiteralPath $invalidManifestRoot -Recurse -Force
}

$burnSelector = [pscustomobject]@{
    streamIndex = 4
    language = 'eng'
    codec = 'hdmv_pgs_subtitle'
    forced = $false
    title = 'English PGS'
}

$burnOverride = [pscustomobject]@{
    subtitles = [pscustomobject]@{
        burnTrack = $burnSelector
    }
}

$configMap = ConvertTo-MediaPipelineFileOverrideConfigMap -Override $burnOverride
Assert-Equal ([string]$configMap['RouteForce']) 'encode' 'Subtitle burn override should force encode.'
Assert-Equal ([string]$configMap['RoutePolicyReason']) 'file override subtitles.burnTrack requires encode' 'Subtitle burn override should record the route reason.'
Assert-Equal ([string]$configMap['SubtitleBurnEncodeProfile']) 'current_encode_style' 'Subtitle burn override should select the current-style burn encode profile.'

$subtitleOverride = $burnOverride.subtitles
Assert-True (-not (Test-SubtitleTrackKeptByOverride -Language 'eng' -IsForced:$false -Title 'English PGS' -Codec 'hdmv_pgs_subtitle' -StreamIndex 4 -SubtitleOverride $subtitleOverride)) 'Burned subtitle should not also be kept as selectable output.'
Assert-True (-not (Test-SubtitleTrackKeptByOverride -Language 'eng' -IsForced:$false -Title 'English SRT' -Codec 'subrip' -StreamIndex 5 -SubtitleOverride $subtitleOverride)) 'Non-burned subtitles should be dropped while burn is active.'
Assert-True (Test-SubtitleTrackBurnedByOverride -Language 'eng' -IsForced:$false -Title 'English PGS' -Codec 'hdmv_pgs_subtitle' -StreamIndex 4 -SubtitleOverride $subtitleOverride) 'Exact burned subtitle selector should match the selected stream.'
Assert-True (-not (Test-SubtitleTrackBurnedByOverride -Language 'eng' -IsForced:$false -Title 'English SRT' -Codec 'subrip' -StreamIndex 5 -SubtitleOverride $subtitleOverride)) 'Burn selector should not match other subtitle streams.'

$remuxBurnOverride = [pscustomobject]@{
    routing = [pscustomobject]@{ profile = 'remux' }
    subtitles = [pscustomobject]@{ burnTrack = $burnSelector }
}
Assert-ThrowsContains -ScriptBlock { ConvertTo-MediaPipelineFileOverrideConfigMap -Override $remuxBurnOverride } -ExpectedText 'routing.profile=remux cannot be combined with subtitles.burnTrack' -Message 'Subtitle burn should reject remux route overrides.'

$missingStreamOverride = [pscustomobject]@{
    subtitles = [pscustomobject]@{
        burnTrack = [pscustomobject]@{
            language = 'eng'
            codec = 'subrip'
        }
    }
}
Assert-ThrowsContains -ScriptBlock { ConvertTo-MediaPipelineFileOverrideConfigMap -Override $missingStreamOverride } -ExpectedText 'subtitles.burnTrack requires an exact streamIndex selector' -Message 'Subtitle burn should require an exact stream index.'

Write-Host 'File override subtitle burn checks passed.'
