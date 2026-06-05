[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Naming support checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent $pipelineRoot

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Remove-PriorityMarkersFromName {
    param([string] $Name)
    $text = [string]$Name
    for ($i = 0; $i -lt 6; $i++) {
        $trimmed = $text.TrimStart()
        if ($trimmed.StartsWith('[NOW]', [System.StringComparison]::OrdinalIgnoreCase)) {
            $text = $trimmed.Substring(5).TrimStart(' ', '-', '_', '.')
            continue
        }
        if ($trimmed.StartsWith('!', [System.StringComparison]::OrdinalIgnoreCase)) {
            $text = $trimmed.Substring(1).TrimStart(' ', '-', '_', '.')
            continue
        }
        break
    }
    return $text.Trim()
}

function Write-Log {
    param($Message, [string] $Level = 'INFO')
    $null = $Message
    $null = $Level
}

function Get-MediaDuration {
    param([string] $Path)
    $null = $Path
    return 123.456
}

function Get-SourceVideoCodec {
    param([string] $Path)
    $null = $Path
    return 'H264'
}

. (Join-Path $repoRoot 'ops\pipeline\engine\naming\naming.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\shared\source_identity.ps1')

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-naming-support-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
try {
    $moviePath = Join-Path $tempRoot 'The.Matrix.1999.1080p.mkv'
    [System.IO.File]::WriteAllBytes($moviePath, [System.Text.Encoding]::UTF8.GetBytes('movie-bytes'))
    $movieInfo = Get-Item -LiteralPath $moviePath

    $moviePlan = New-PlexDestinationPlan -MediaKind Movie -File $movieInfo -OriginalName $movieInfo.Name -Extension 'mkv' -IncludeLibraryFolder
    Assert-Equal $moviePlan.FileName 'The Matrix (1999).mkv' 'Movie destination planner should scrub release tags and preserve year.'
    Assert-Equal $moviePlan.RelativePath (Join-Path 'Movies\The Matrix (1999)' 'The Matrix (1999).mkv') 'Movie relative path should use the shared Plex planner.'

    $script:RenameMovieFilterOptions = @{
        video_source = $true
        audio_channels = $true
        editions = $true
        file_size = $true
        services_containers = $true
        release_groups = $true
    }
    $script:RenameMovieFilterTerms = @{
        release_groups = @('SupaCvnt', 'BYNDR')
        services_containers = @('MA')
    }
    $script:RenameMovieRemoveTerms = @('sample', 'trailer', 'extras', 'featurette', 'deleted scenes', 'behind the scenes')
    $ironLungPlan = New-PlexMovieDestinationPlan -OriginalName 'Iron.Lung.2026.1080p.WEBRip.x265.6CH-SupaCvnt.mkv' -Extension 'mkv'
    $hoppersPlan = New-PlexMovieDestinationPlan -OriginalName 'Hoppers.2026.2160p.MA.WEB-DL.DDP5.1.Atmos.DV.HDR.H.265-BYNDR.mkv' -Extension 'mkv'
    Assert-Equal $ironLungPlan.FileName 'Iron Lung (2026).mkv' 'Saved rename filter policy should remove custom Iron Lung release group terms.'
    Assert-Equal $hoppersPlan.FileName 'Hoppers (2026).mkv' 'Saved rename filter policy should remove custom Hoppers service and release-group terms.'
    Remove-Variable -Name RenameMovieFilterOptions -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name RenameMovieFilterTerms -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name RenameMovieRemoveTerms -Scope Script -ErrorAction SilentlyContinue

    $overridePath = Get-RenameOverrideSidecarPath -File $movieInfo
    $overridePayload = [ordered]@{
        RenameTool = [ordered]@{
            ForcePipelineName = $true
            FinalName = '..\Forced Matrix Name.mkv'
        }
    } | ConvertTo-Json -Depth 5
    Set-Content -LiteralPath $overridePath -Value $overridePayload -Encoding UTF8

    $forcedPlan = New-PlexDestinationPlan -MediaKind Movie -File $movieInfo -OriginalName $movieInfo.Name -Extension 'mkv' -IncludeLibraryFolder
    Assert-True ([bool]$forcedPlan.RenameOverrideApplied) 'Forced rename sidecar should mark the destination plan.'
    Assert-Equal $forcedPlan.FileName 'Forced Matrix Name.mkv' 'Forced rename sidecar should use only the sanitized final-name leaf.'
    Assert-Equal $forcedPlan.RenameOverrideSidecar $overridePath 'Forced rename sidecar path should be recorded as evidence.'
    Assert-True (-not ([string]$forcedPlan.RelativePath).Contains('..')) 'Forced rename sidecar must not inject parent path traversal into relative output paths.'

    $showFolder = Join-Path $tempRoot 'Example Show\Season 02'
    New-Item -ItemType Directory -Path $showFolder -Force | Out-Null
    $tvPath = Join-Path $showFolder 'Example.Show.S02E03 - Pilot.mkv'
    [System.IO.File]::WriteAllBytes($tvPath, [System.Text.Encoding]::UTF8.GetBytes('tv-bytes'))
    $tvInfo = Get-TVInfoFromFile (Get-Item -LiteralPath $tvPath)
    $tvPlan = New-PlexDestinationPlan -MediaKind TV -File (Get-Item -LiteralPath $tvPath) -TvInfo $tvInfo -OriginalName $tvInfo.OriginalName -Extension 'mkv' -IncludeLibraryFolder

    Assert-Equal $tvInfo.Season 2 'TV parser should read SxxEyy season.'
    Assert-Equal $tvInfo.Episode 3 'TV parser should read SxxEyy episode.'
    Assert-Equal $tvPlan.RelativePath (Join-Path 'TV\Example Show\Season 02' 'Example Show - S02E03 - Pilot.mkv') 'TV destination planner should produce Plex show/season/file path.'
    Assert-Equal $tvPlan.IdentityKey 'Example Show_S02E03' 'TV destination planner identity key should match library index keys.'

    $sourceA = Join-Path $tempRoot 'IdentityA.mkv'
    $sourceB = Join-Path $tempRoot 'IdentityB.mkv'
    [System.IO.File]::WriteAllBytes($sourceA, [System.Text.Encoding]::UTF8.GetBytes('same-size-a'))
    [System.IO.File]::WriteAllBytes($sourceB, [System.Text.Encoding]::UTF8.GetBytes('same-size-a'))

    $identityA = Get-SourceIdentityKeyV2 (Get-Item -LiteralPath $sourceA)
    $identityB = Get-SourceIdentityKeyV2 (Get-Item -LiteralPath $sourceB)
    Assert-Equal $identityB $identityA 'Source identity v2 should not depend on source path when size, media facts, and sample bytes match.'

    [System.IO.File]::WriteAllBytes($sourceB, [System.Text.Encoding]::UTF8.GetBytes('same-size-b'))
    $changedIdentityB = Get-SourceIdentityKeyV2 (Get-Item -LiteralPath $sourceB)
    Assert-True ($changedIdentityB -ne $identityA) 'Source identity v2 should change when same-size source sample bytes change.'
    Assert-True (Test-LegacySourceIdentityV2Algorithm 'path-size-mtime-v1') 'Legacy source identity algorithm aliases should be detected.'
    Assert-True (-not (Test-LegacySourceIdentityV2Algorithm 'identity-v2')) 'Current source identity algorithm should not be treated as legacy.'
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host 'Naming support checks passed.'
