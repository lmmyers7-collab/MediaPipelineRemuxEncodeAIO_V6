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
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSCommandPath."
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -PathType Container)) {
    throw "Resolved repository root is missing ops\pipeline\engine: $repoRoot"
}

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
        languages_subs_dubs = $true
        release_groups = $true
    }
    $script:RenameMovieFilterTerms = @{
        release_groups = @('SupaCvnt', 'BYNDR', 'YIFY', 'YTS.AM', 'YTS.MX', 'BONE')
        services_containers = @('MA')
        languages_subs_dubs = @('ita', 'eng', 'sub', 'dub')
    }
    $script:RenameMovieRemoveTerms = @('sample', 'trailer', 'extras', 'featurette', 'deleted scenes', 'behind the scenes')
    $ironLungPlan = New-PlexMovieDestinationPlan -OriginalName 'Iron.Lung.2026.1080p.WEBRip.x265.6CH-SupaCvnt.mkv' -Extension 'mkv'
    $hoppersPlan = New-PlexMovieDestinationPlan -OriginalName 'Hoppers.2026.2160p.MA.WEB-DL.DDP5.1.Atmos.DV.HDR.H.265-BYNDR.mkv' -Extension 'mkv'
    $languageTagPlan = New-PlexMovieDestinationPlan -OriginalName 'Cinema.Paradiso.1988.Ita.Eng.Sub.Dub.1080p.BluRay.x264.mkv' -Extension 'mkv'
    Assert-Equal $ironLungPlan.FileName 'Iron Lung (2026).mkv' 'Saved rename filter policy should remove custom Iron Lung release group terms.'
    Assert-Equal $hoppersPlan.FileName 'Hoppers (2026).mkv' 'Saved rename filter policy should remove custom Hoppers service and release-group terms.'
    Assert-Equal $languageTagPlan.FileName 'Cinema Paradiso (1988).mkv' 'Saved rename filter policy should remove language and sub-dub release tags.'
    $strictMovieCases = [ordered]@{
        'The.Lord.Of.The.Rings.The.War.Of.The.Rohirrim.2024.1080p.WEBRip.10Bit.DDP5.1.x265-Asiimov.mkv' = 'The Lord of the Rings The War of the Rohirrim (2024).mkv'
        'Mortal.Kombat.II.2026.1080p.WEBRip.AAC5.1.10bits.x265-Rapta.mkv' = 'Mortal Kombat II (2026).mkv'
        'Cast Away (2000) UpScaled 2160p H265 10 bit DV HDR10+ ita eng AC3 5.1 sub ita eng Licdom.mkv' = 'Cast Away (2000).mkv'
        # GalaxyRG265 is intentionally not configured as an exact or custom
        # term. A technical anchor makes the whole release-metadata tail non-title text.
        'Edge.of.Tomorrow.2014.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265.mkv' = 'Edge of Tomorrow (2014).mkv'
        'Django.Unchained.2012.1080p.BluRay.x264.YIFY.mp4' = 'Django Unchained (2012).mp4'
        'Furiosa.A.Mad.Max.Saga.2024.1080p.BluRay.x264.AAC5.1-[YTS.MX].mp4' = 'Furiosa A Mad Max Saga (2024).mp4'
        'Hereditary.2018.1080p.BluRay.x264-[YTS.AM].mp4' = 'Hereditary (2018).mp4'
        'Jabberwocky 1977 1080p Criterion BluRay HEVC x265 5.1 BONE.mkv' = 'Jabberwocky (1977).mkv'
        'Obsession 2026 1080p WEB-DL HEVC x265 5.1 BONE.mkv' = 'Obsession (2026).mkv'
        'The.Fast.and.the.Furious.Tokyo.Drift.2011.1080p.BrRip.x264.YIFY.mp4' = 'The Fast and the Furious Tokyo Drift (2011).mp4'
    }
    foreach ($case in $strictMovieCases.GetEnumerator()) {
        $caseExtension = [System.IO.Path]::GetExtension([string]$case.Key).TrimStart('.')
        $plan = New-PlexMovieDestinationPlan -OriginalName $case.Key -Extension $caseExtension
        Assert-Equal $plan.FileName $case.Value "Strict movie rename filters should scrub leaked release metadata from '$($case.Key)'."
    }
    $baseMovieRemoveTerms = @('sample', 'trailer', 'extras', 'featurette', 'deleted scenes', 'behind the scenes')
    $legacyPackagedMovieRemoveTerms = @($baseMovieRemoveTerms) + @(1..12 | ForEach-Object { $_.ToString('00') })
    $script:RenameMovieRemoveTerms = $legacyPackagedMovieRemoveTerms
    Assert-Equal (@(Get-NamingRenameMovieRemoveTerms) -join '|') ($baseMovieRemoveTerms -join '|') 'The exact legacy packaged movie remove-term list should normalize away its unsafe 01-12 entries in memory.'
    $legacyPackagedNumericTitlePlan = New-PlexMovieDestinationPlan -OriginalName '12.Angry.Men.1957.1080p.BluRay.x264.mkv' -Extension 'mkv'
    Assert-Equal $legacyPackagedNumericTitlePlan.FileName '12 Angry Men (1957).mkv' 'The exact legacy packaged remove-term list must not strip a numeric movie title during PowerShell naming.'
    $script:RenameMovieRemoveTerms = @('sample', '01')
    Assert-Equal (@(Get-NamingRenameMovieRemoveTerms) -join '|') 'sample|01' 'A customized subset of legacy movie remove terms must remain unchanged.'
    $script:RenameMovieRemoveTerms = @($legacyPackagedMovieRemoveTerms) + @('workprint')
    Assert-Equal (@(Get-NamingRenameMovieRemoveTerms) -join '|') (($legacyPackagedMovieRemoveTerms + @('workprint')) -join '|') 'A customized superset of legacy movie remove terms must remain unchanged.'
    $script:RenameMovieRemoveTerms = $baseMovieRemoveTerms

    $numericMovieTitleCases = [ordered]@{
        '2001.A.Space.Odyssey.1968.1080p.BluRay.x264.mkv' = '2001 A Space Odyssey (1968).mkv'
        'Blade.Runner.2049.2017.1080p.BluRay.x264.mkv' = 'Blade Runner 2049 (2017).mkv'
        '1917.2019.1080p.BluRay.x264.mkv' = '1917 (2019).mkv'
        '1984.1984.1080p.BluRay.x264.mkv' = '1984 (1984).mkv'
        '12.Angry.Men.1957.1080p.BluRay.x264.mkv' = '12 Angry Men (1957).mkv'
        '10.Cloverfield.Lane.2016.1080p.BluRay.x264.mkv' = '10 Cloverfield Lane (2016).mkv'
        'Roundhay.Garden.Scene.1888.mkv' = 'Roundhay Garden Scene (1888).mkv'
        'Movie.(2020).2021.mkv' = 'Movie 2021 (2020).mkv'
    }
    foreach ($case in $numericMovieTitleCases.GetEnumerator()) {
        $plan = New-PlexMovieDestinationPlan -OriginalName $case.Key -Extension 'mkv'
        Assert-Equal $plan.FileName $case.Value "Movie naming should use the rightmost release year and preserve numeric title text in '$($case.Key)'."
    }
    $futureTitleYear = (Get-Date).Year + 2
    $farFutureTitlePlan = New-PlexMovieDestinationPlan -OriginalName "Far.Future.$futureTitleYear.mkv" -Extension 'mkv'
    Assert-Equal $farFutureTitlePlan.FileName "Far Future $futureTitleYear.mkv" 'A year-like number beyond next year should remain title text rather than becoming release-year metadata.'
    $currentNumericTitle = (Get-Date).Year
    $loneNumericTitlePlan = New-PlexMovieDestinationPlan -OriginalName "$currentNumericTitle.mkv" -Extension 'mkv'
    Assert-Equal $loneNumericTitlePlan.FileName "$currentNumericTitle.mkv" 'A lone plausible current-year number should remain a numeric movie title.'

    $ambiguousMovieTitleCases = [ordered]@{
        'Web.2024.mkv' = 'Web (2024).mkv'
        'Cam.2018.mkv' = 'Cam (2018).mkv'
        'DC.League.of.Super-Pets.2022.mkv' = 'DC League of Super-Pets (2022).mkv'
        'Ma.2019.mkv' = 'Ma (2019).mkv'
        'Audio.2017.mkv' = 'Audio (2017).mkv'
        'A.Proper.Man.2024.mkv' = 'A Proper Man (2024).mkv'
    }
    foreach ($case in $ambiguousMovieTitleCases.GetEnumerator()) {
        $plan = New-PlexMovieDestinationPlan -OriginalName $case.Key -Extension 'mkv'
        Assert-Equal $plan.FileName $case.Value "Ambiguous metadata-like words should be preserved when they are legitimate movie title text in '$($case.Key)'."
    }

    $verifiedTailCases = [ordered]@{
        'Movie.PROPER.2024.mkv' = 'Movie (2024).mkv'
        'Movie.REPACK.2024.mkv' = 'Movie (2024).mkv'
        'Movie.RERIP.2024.mkv' = 'Movie (2024).mkv'
        'Movie.2024.WEB.CAM.DC.MA.Dual.Audio.PROPER.REPACK.RERIP.1080p.mkv' = 'Movie (2024).mkv'
    }
    foreach ($case in $verifiedTailCases.GetEnumerator()) {
        $plan = New-PlexMovieDestinationPlan -OriginalName $case.Key -Extension 'mkv'
        Assert-Equal $plan.FileName $case.Value "Verified release-tail metadata should be removed from '$($case.Key)'."
    }

    $script:RenameMovieFilterOptions['services_containers'] = $false
    $disabledCustomMovieTermPlan = New-PlexMovieDestinationPlan -OriginalName 'Example.Movie.2024.MA.WEB-DL.1080p.mkv' -Extension 'mkv'
    Assert-Equal $disabledCustomMovieTermPlan.FileName 'Example Movie MA (2024).mkv' 'A configured custom movie term should remain when its cleaning category is disabled.'
    $script:RenameMovieFilterOptions['services_containers'] = $true
    $enabledCustomMovieTermPlan = New-PlexMovieDestinationPlan -OriginalName 'Example.Movie.2024.MA.WEB-DL.1080p.mkv' -Extension 'mkv'
    Assert-Equal $enabledCustomMovieTermPlan.FileName 'Example Movie (2024).mkv' 'A configured custom movie term should be removed from a verified release tail when its category is enabled.'
    Assert-Equal (Get-CleanMovieName '1080p.WEB-DL.x265.2024.mkv') '' 'A metadata-only movie name should clean to an empty title instead of leaking raw release metadata.'
    $metadataOnlyMoviePlan = New-PlexMovieDestinationPlan -OriginalName '1080p.WEB-DL.x265.2024.mkv' -Extension 'mkv'
    Assert-Equal $metadataOnlyMoviePlan.FileName 'Unknown Movie.mkv' 'Production destination planning should use the safe Unknown Movie fallback when movie cleaning yields no title.'
    Remove-Variable -Name RenameMovieFilterOptions -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name RenameMovieFilterTerms -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name RenameMovieRemoveTerms -Scope Script -ErrorAction SilentlyContinue

    $script:RenameTVFilterOptions = @{
        video_source = $true
        audio_channels = $true
        release_flags = $true
        services_containers = $true
        languages_subs_dubs = $true
        release_groups = $true
    }
    $script:RenameTVFilterTerms = @{
        video_source = @('MoonSource')
        release_groups = @('Judas', 'SubsPlease', 'ToonsHub')
    }
    $script:RenameTVRemoveTerms = @('UnwantedLeaf')
    Assert-Equal (Get-CleanTVOutputNamePart 'Example Show MoonSource') 'Example Show' 'TV naming should remove a configured custom term when every filter category is enabled.'
    $script:RenameTVFilterOptions['video_source'] = $false
    Assert-Equal (Get-CleanTVOutputNamePart 'Example Show MoonSource') 'Example Show MoonSource' 'TV naming should preserve a configured term when its category is disabled.'
    $script:RenameTVFilterOptions['video_source'] = $true
    Assert-Equal (Get-CleanTVOutputNamePart 'Example Show UnwantedLeaf') 'Example Show' 'TV naming should remove configured TV custom remove terms.'
    Remove-Variable -Name RenameTVFilterOptions -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name RenameTVFilterTerms -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name RenameTVRemoveTerms -Scope Script -ErrorAction SilentlyContinue

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

    $episode100Path = Join-Path $showFolder 'Example.Show.S01E100 - Century.mkv'
    [System.IO.File]::WriteAllBytes($episode100Path, [System.Text.Encoding]::UTF8.GetBytes('episode-100-bytes'))
    $episode100Info = Get-TVInfoFromFile (Get-Item -LiteralPath $episode100Path)
    $episode100Plan = New-PlexDestinationPlan -MediaKind TV -File (Get-Item -LiteralPath $episode100Path) -TvInfo $episode100Info -OriginalName $episode100Info.OriginalName -Extension 'mkv' -IncludeLibraryFolder
    Assert-True ([bool]$episode100Info.IsReliable) 'Canonical TV identities should accept three-digit episode numbers through E999.'
    Assert-Equal $episode100Info.Episode 100 'Canonical E100 must not be truncated to E10.'
    Assert-Equal $episode100Plan.FileName 'Example Show - S01E100 - Century.mkv' 'TV destination naming should retain a valid three-digit episode identity.'

    $episode1000Path = Join-Path $showFolder 'Example.Show.S01E1000.mkv'
    [System.IO.File]::WriteAllBytes($episode1000Path, [System.Text.Encoding]::UTF8.GetBytes('episode-1000-bytes'))
    $previousAggressiveEpisodeParsing = $script:AggressiveEpisodeParsing
    $script:AggressiveEpisodeParsing = $false
    try {
        $episode1000Info = Get-TVInfoFromFile (Get-Item -LiteralPath $episode1000Path)
    } finally {
        $script:AggressiveEpisodeParsing = $previousAggressiveEpisodeParsing
    }
    Assert-True (-not [bool]$episode1000Info.IsReliable) 'Canonical-looking E1000 must be rejected instead of being truncated to a smaller episode number.'
    Assert-True ($null -eq $episode1000Info.EpisodeEnd) 'An out-of-range episode token must not create a range endpoint.'

    foreach ($rangeName in @(
        'Example.Show.S01E01E02.mkv',
        'Example.Show.S01E01-E02.mkv',
        'Example.Show.S01E01_E02.mkv',
        'Example.Show.S01E01-E02v2.mkv'
    )) {
        $rangePath = Join-Path $showFolder $rangeName
        [System.IO.File]::WriteAllBytes($rangePath, [System.Text.Encoding]::UTF8.GetBytes("range-$rangeName"))
        $rangeInfo = Get-TVInfoFromFile (Get-Item -LiteralPath $rangePath)
        $rangePlan = New-PlexDestinationPlan -MediaKind TV -File (Get-Item -LiteralPath $rangePath) -TvInfo $rangeInfo -OriginalName $rangeInfo.OriginalName -Extension 'mkv' -IncludeLibraryFolder
        Assert-True ([bool]$rangeInfo.IsReliable) "Canonical multi-episode variant '$rangeName' should parse reliably."
        Assert-Equal $rangeInfo.Season 1 "Canonical multi-episode variant '$rangeName' should preserve the season."
        Assert-Equal $rangeInfo.Episode 1 "Canonical multi-episode variant '$rangeName' should preserve the first episode."
        Assert-Equal $rangeInfo.EpisodeEnd 2 "Canonical multi-episode variant '$rangeName' should preserve the final episode."
        Assert-Equal $rangePlan.FileName 'Example Show - S01E01-E02.mkv' "Canonical multi-episode variant '$rangeName' should normalize to one Plex filename form."
        Assert-Equal $rangePlan.IdentityKey 'Example Show_S01E01-E02' "Canonical multi-episode variant '$rangeName' should include the final episode in its identity key."
    }

    foreach ($invalidRangeName in @(
        'Example.Show.S01E01-E01.mkv',
        'Example.Show.S01E02-E01.mkv',
        'Example.Show.S01E01-E1000.mkv'
    )) {
        $invalidRangePath = Join-Path $showFolder $invalidRangeName
        [System.IO.File]::WriteAllBytes($invalidRangePath, [System.Text.Encoding]::UTF8.GetBytes("invalid-range-$invalidRangeName"))
        $invalidRangeInfo = Get-TVInfoFromFile (Get-Item -LiteralPath $invalidRangePath)
        Assert-True (-not [bool]$invalidRangeInfo.IsReliable) "Invalid, equal, or reversed range '$invalidRangeName' must be blocked rather than silently normalized."
        Assert-True ($null -eq $invalidRangeInfo.EpisodeEnd) "Invalid, equal, or reversed range '$invalidRangeName' must not set an episode range endpoint."
        Assert-True ([string]$invalidRangeInfo.ParseError -match 'SxxEyy-Ezz') "Invalid, equal, or reversed range '$invalidRangeName' should explain the required canonical increasing range form."
    }

    $revisionTitlePath = Join-Path $showFolder 'Example.Show.S01E12v3 - Revision Title.mkv'
    [System.IO.File]::WriteAllBytes($revisionTitlePath, [System.Text.Encoding]::UTF8.GetBytes('revision-title-bytes'))
    $revisionTitleInfo = Get-TVInfoFromFile (Get-Item -LiteralPath $revisionTitlePath)
    $revisionTitlePlan = New-PlexDestinationPlan -MediaKind TV -File (Get-Item -LiteralPath $revisionTitlePath) -TvInfo $revisionTitleInfo -OriginalName $revisionTitleInfo.OriginalName -Extension 'mkv' -IncludeLibraryFolder
    Assert-Equal $revisionTitleInfo.Revision 3 'Uploader revision metadata should be captured separately from the canonical episode identity.'
    Assert-Equal $revisionTitlePlan.FileName 'Example Show - S01E12 - Revision Title.mkv' 'Uploader revisions should be removed without dropping the legitimate episode title.'

    $properTitlePath = Join-Path $showFolder 'Example.Show.S01E13 - A Proper Introduction.mkv'
    [System.IO.File]::WriteAllBytes($properTitlePath, [System.Text.Encoding]::UTF8.GetBytes('proper-title-bytes'))
    $properTitleInfo = Get-TVInfoFromFile (Get-Item -LiteralPath $properTitlePath)
    $properTitlePlan = New-PlexDestinationPlan -MediaKind TV -File (Get-Item -LiteralPath $properTitlePath) -TvInfo $properTitleInfo -OriginalName $properTitleInfo.OriginalName -Extension 'mkv' -IncludeLibraryFolder
    Assert-Equal $properTitlePlan.FileName 'Example Show - S01E13 - A Proper Introduction.mkv' 'PROPER-like words inside a legitimate episode title must be preserved.'

    $internalTitlePath = Join-Path $showFolder 'The.Web.S01E14 - Internal Affairs.mkv'
    [System.IO.File]::WriteAllBytes($internalTitlePath, [System.Text.Encoding]::UTF8.GetBytes('internal-title-bytes'))
    $internalTitleInfo = Get-TVInfoFromFile (Get-Item -LiteralPath $internalTitlePath)
    $internalTitlePlan = New-PlexDestinationPlan -MediaKind TV -File (Get-Item -LiteralPath $internalTitlePath) -TvInfo $internalTitleInfo -OriginalName $internalTitleInfo.OriginalName -Extension 'mkv' -IncludeLibraryFolder
    Assert-Equal $internalTitlePlan.FileName 'The Web - S01E14 - Internal Affairs.mkv' 'Metadata-like words inside legitimate TV show and episode titles must be preserved.'

    $numericTitlePath = Join-Path $showFolder 'Example.Show.S01E15 - 12345.mkv'
    [System.IO.File]::WriteAllBytes($numericTitlePath, [System.Text.Encoding]::UTF8.GetBytes('numeric-title-bytes'))
    $numericTitleInfo = Get-TVInfoFromFile (Get-Item -LiteralPath $numericTitlePath)
    $numericTitlePlan = New-PlexDestinationPlan -MediaKind TV -File (Get-Item -LiteralPath $numericTitlePath) -TvInfo $numericTitleInfo -OriginalName $numericTitleInfo.OriginalName -Extension 'mkv' -IncludeLibraryFolder
    Assert-Equal $numericTitlePlan.FileName 'Example Show - S01E15.mkv' 'Purely numeric episode titles should be rejected consistently.'

    $numericLexicalTitlePath = Join-Path $showFolder 'Example.Show.S01E16 - 123 Reasons.mkv'
    [System.IO.File]::WriteAllBytes($numericLexicalTitlePath, [System.Text.Encoding]::UTF8.GetBytes('numeric-lexical-title-bytes'))
    $numericLexicalTitleInfo = Get-TVInfoFromFile (Get-Item -LiteralPath $numericLexicalTitlePath)
    $numericLexicalTitlePlan = New-PlexDestinationPlan -MediaKind TV -File (Get-Item -LiteralPath $numericLexicalTitlePath) -TvInfo $numericLexicalTitleInfo -OriginalName $numericLexicalTitleInfo.OriginalName -Extension 'mkv' -IncludeLibraryFolder
    Assert-Equal $numericLexicalTitlePlan.FileName 'Example Show - S01E16 - 123 Reasons.mkv' 'Numeric-leading lexical episode titles should remain authoritative.'

    $bookwormFolder = Join-Path $tempRoot 'Ascendance of a Bookworm S03+SP 1080p Dual Audio BD Remux FLAC-TTGA'
    New-Item -ItemType Directory -Path $bookwormFolder -Force | Out-Null
    $bookwormPath = Join-Path $bookwormFolder 'S03E01-The Beginning of Winter.mkv'
    [System.IO.File]::WriteAllBytes($bookwormPath, [System.Text.Encoding]::UTF8.GetBytes('bookworm-bytes'))
    $bookwormInfo = Get-TVInfoFromFile (Get-Item -LiteralPath $bookwormPath)
    $bookwormPlan = New-PlexDestinationPlan -MediaKind TV -File (Get-Item -LiteralPath $bookwormPath) -TvInfo $bookwormInfo -OriginalName $bookwormInfo.OriginalName -Extension 'mkv' -IncludeLibraryFolder
    Assert-Equal $bookwormInfo.ShowName 'Ascendance of a Bookworm' 'TV folder parser should scrub +SP release metadata and TTGA from show folder names.'
    Assert-Equal $bookwormInfo.Season 3 'TV parser should preserve season from S03+SP source folders.'
    Assert-Equal $bookwormInfo.Episode 1 'TV parser should read episode from S03E01 source file.'
    Assert-Equal $bookwormPlan.RelativePath (Join-Path 'TV\Ascendance of a Bookworm\Season 03' 'Ascendance of a Bookworm - S03E01 - The Beginning of Winter.mkv') 'TV destination planner should keep release metadata out of Bookworm output paths.'

    $rootTvFolder = Join-Path $tempRoot 'TV'
    New-Item -ItemType Directory -Path $rootTvFolder -Force | Out-Null
    $reZeroName = '[Erai-raws] Re Zero kara Hajimeru Isekai Seikatsu 4th Season - 01 [1080p CR WEBRip HEVC AAC][MultiSub][C86350AC].mkv'
    $reZeroPath = Join-Path $rootTvFolder $reZeroName
    [System.IO.File]::WriteAllBytes($reZeroPath, [System.Text.Encoding]::UTF8.GetBytes('rezero-bytes'))
    $reZeroInfo = Get-TVInfoFromFile -file (Get-Item -LiteralPath $reZeroPath) -SourceRootPath $rootTvFolder -LibraryName 'TV' -LibraryId 'tv' -LibraryDesignation 'tv'
    $reZeroPlan = New-PlexDestinationPlan -MediaKind TV -File (Get-Item -LiteralPath $reZeroPath) -TvInfo $reZeroInfo -OriginalName $reZeroInfo.OriginalName -Extension 'mkv' -IncludeLibraryFolder
    Assert-Equal $reZeroInfo.ShowName 'Re Zero kara Hajimeru Isekai Seikatsu' 'Root-level ordinal-season TV parser should extract the show title before falling back to the TV source folder.'
    Assert-Equal $reZeroInfo.Season 4 'Root-level ordinal-season TV parser should read numeric ordinal seasons.'
    Assert-Equal $reZeroInfo.Episode 1 'Root-level ordinal-season TV parser should read bare episode numbers after the season token.'
    Assert-Equal $reZeroInfo.ParseMode 'ordinal-season' 'Root-level ordinal-season TV parser should keep the explicit ordinal parse mode.'
    Assert-Equal $reZeroPlan.RelativePath (Join-Path 'TV\Re Zero kara Hajimeru Isekai Seikatsu\Season 04' 'Re Zero kara Hajimeru Isekai Seikatsu - S04E01.mkv') 'TV destination planner should not create TV\TV for root-level ordinal-season fansub files.'

    $thirdCourPath = Join-Path $rootTvFolder 'Example Show 3rd Cour - 01.mkv'
    [System.IO.File]::WriteAllBytes($thirdCourPath, [System.Text.Encoding]::UTF8.GetBytes('third-cour-bytes'))
    $thirdCourInfo = Get-TVInfoFromFile -file (Get-Item -LiteralPath $thirdCourPath) -SourceRootPath $rootTvFolder -LibraryName 'TV' -LibraryId 'tv' -LibraryDesignation 'tv'
    Assert-True ([bool]$thirdCourInfo.IsReliable) 'Ordinal cour markers should provide a reliable season when paired with a bare episode number.'
    Assert-Equal $thirdCourInfo.ShowName 'Example Show' 'Ordinal cour parsing should remove the season marker from the show name.'
    Assert-Equal $thirdCourInfo.Season 3 'The 3rd Cour marker should map to season 3.'
    Assert-Equal $thirdCourInfo.Episode 1 'Ordinal cour parsing should retain the bare episode number.'

    $specialShowRoot = Join-Path $rootTvFolder 'Example Show'
    New-Item -ItemType Directory -Path $specialShowRoot -Force | Out-Null
    $filenameSpecialPath = Join-Path $specialShowRoot 'Example Show OVA - E01.mkv'
    [System.IO.File]::WriteAllBytes($filenameSpecialPath, [System.Text.Encoding]::UTF8.GetBytes('filename-special-bytes'))
    $filenameSpecialInfo = Get-TVInfoFromFile -file (Get-Item -LiteralPath $filenameSpecialPath) -SourceRootPath $rootTvFolder -LibraryName 'TV' -LibraryId 'tv' -LibraryDesignation 'tv'
    $filenameSpecialPlan = New-PlexDestinationPlan -MediaKind TV -File (Get-Item -LiteralPath $filenameSpecialPath) -TvInfo $filenameSpecialInfo -OriginalName $filenameSpecialInfo.OriginalName -Extension 'mkv' -IncludeLibraryFolder
    Assert-True ([bool]$filenameSpecialInfo.IsReliable) 'Filename OVA markers paired with an episode token should parse reliably.'
    Assert-Equal $filenameSpecialInfo.Season 0 'A filename OVA marker should map to the specials season.'
    Assert-Equal $filenameSpecialPlan.RelativePath (Join-Path 'TV\Example Show\Specials' 'Example Show - S00E01.mkv') 'Season zero TV destinations should use the Plex Specials folder.'

    $explicitSeasonSpecialPath = Join-Path $specialShowRoot 'Example Show OVA S02E01.mkv'
    [System.IO.File]::WriteAllBytes($explicitSeasonSpecialPath, [System.Text.Encoding]::UTF8.GetBytes('explicit-season-special-bytes'))
    $explicitSeasonSpecialInfo = Get-TVInfoFromFile -file (Get-Item -LiteralPath $explicitSeasonSpecialPath) -SourceRootPath $rootTvFolder -LibraryName 'TV' -LibraryId 'tv' -LibraryDesignation 'tv'
    Assert-Equal $explicitSeasonSpecialInfo.Season 2 'An explicit SxxEyy identity should take precedence over a filename OVA marker.'
    Assert-Equal $explicitSeasonSpecialInfo.Episode 1 'An explicit SxxEyy identity should retain its episode when OVA also appears in the filename.'

    $libraryFallbackPath = Join-Path $rootTvFolder 'S01E01.mkv'
    [System.IO.File]::WriteAllBytes($libraryFallbackPath, [System.Text.Encoding]::UTF8.GetBytes('library-fallback-bytes'))
    $libraryFallbackInfo = Get-TVInfoFromFile -file (Get-Item -LiteralPath $libraryFallbackPath) -SourceRootPath $rootTvFolder -LibraryName 'TV' -LibraryId 'tv' -LibraryDesignation 'tv'
    Assert-True (-not $libraryFallbackInfo.IsReliable) 'Root-level TV files must not use the TV library/root name as a show name.'
    Assert-Equal $libraryFallbackInfo.ParseMode 'library-fallback-blocked' 'Library/root fallback should be blocked with an explicit parse mode.'
    Assert-True ($libraryFallbackInfo.ParseError -match 'library/root label') 'Library/root fallback should explain why the TV parse was blocked.'

    $validShowRoot = Join-Path $rootTvFolder 'Valid Show'
    New-Item -ItemType Directory -Path $validShowRoot -Force | Out-Null
    $validShowPath = Join-Path $validShowRoot 'S01E01.mkv'
    [System.IO.File]::WriteAllBytes($validShowPath, [System.Text.Encoding]::UTF8.GetBytes('valid-show-bytes'))
    $validShowInfo = Get-TVInfoFromFile -file (Get-Item -LiteralPath $validShowPath) -SourceRootPath $rootTvFolder -LibraryName 'TV' -LibraryId 'tv' -LibraryDesignation 'tv'
    Assert-True ([bool]$validShowInfo.IsReliable) 'TV files under a show folder should remain reliable when the library root is TV.'
    Assert-Equal $validShowInfo.ShowName 'Valid Show' 'Show-folder fallback should still provide the show name.'
    Assert-Equal $validShowInfo.Season 1 'Show-folder fallback should preserve SxxEyy season.'
    Assert-Equal $validShowInfo.Episode 1 'Show-folder fallback should preserve SxxEyy episode.'

    $kananRoot = Join-Path $rootTvFolder 'Kanan-sama wa Akumade Choroi'
    New-Item -ItemType Directory -Path $kananRoot -Force | Out-Null
    foreach ($episodeName in @('09', '10', '11')) {
        $siblingPath = Join-Path $kananRoot "[SubsPlease] Kanan-sama wa Akumade Choroi - $episodeName (1080p) [TEST$episodeName].mkv"
        [System.IO.File]::WriteAllBytes($siblingPath, [System.Text.Encoding]::UTF8.GetBytes("kanan-$episodeName"))
    }
    $kananRevisionPath = Join-Path $kananRoot '[SubsPlease] Kanan-sama wa Akumade Choroi - 12v2 (1080p) [80A8418A].mkv'
    [System.IO.File]::WriteAllBytes($kananRevisionPath, [System.Text.Encoding]::UTF8.GetBytes('kanan-12v2'))
    $script:AggressiveEpisodeParsing = $true
    $kananRevisionInfo = Get-TVInfoFromFile -file (Get-Item -LiteralPath $kananRevisionPath) -SourceRootPath $rootTvFolder -LibraryName 'TV' -LibraryId 'tv' -LibraryDesignation 'tv'
    Assert-True ([bool]$kananRevisionInfo.IsReliable) ("Uploader revision suffixes such as 12v2 should not block TV dry-run parsing: " + [string]$kananRevisionInfo.ParseError)
    Assert-Equal $kananRevisionInfo.Season 1 'Uploader revision suffixes should preserve the default TV season.'
    Assert-Equal $kananRevisionInfo.Episode 12 'Uploader revision suffixes should preserve the episode number.'
    Assert-Equal $kananRevisionInfo.Revision 2 'Uploader revision suffixes should be retained as identity evidence rather than title text.'
    $kananRevisionPlan = New-PlexDestinationPlan -MediaKind TV -File (Get-Item -LiteralPath $kananRevisionPath) -TvInfo $kananRevisionInfo -OriginalName $kananRevisionInfo.OriginalName -Extension 'mkv' -IncludeLibraryFolder
    Assert-Equal $kananRevisionPlan.RelativePath (Join-Path 'TV\Kanan-sama wa Akumade Choroi\Season 01' 'Kanan-sama wa Akumade Choroi - S01E12.mkv') 'The exact real-world Queue fixture should resolve to the same clean Plex destination outside the Queue snapshot schema.'

    $genericAnimeRoot = Join-Path $rootTvFolder 'Anime'
    New-Item -ItemType Directory -Path $genericAnimeRoot -Force | Out-Null
    $genericKananPath = Join-Path $genericAnimeRoot '[SubsPlease] Kanan-sama wa Akumade Choroi - 12v2 (1080p) [80A8418A].mkv'
    [System.IO.File]::WriteAllBytes($genericKananPath, [System.Text.Encoding]::UTF8.GetBytes('generic-folder-kanan-12v2'))
    $genericKananInfo = Get-TVInfoFromFile -file (Get-Item -LiteralPath $genericKananPath) -SourceRootPath $rootTvFolder -LibraryName 'TV' -LibraryId 'tv' -LibraryDesignation 'tv'
    Assert-True ([bool]$genericKananInfo.IsReliable) 'A credible anime-style bare revision token should parse under a generic source folder.'
    Assert-Equal $genericKananInfo.ShowName 'Kanan-sama wa Akumade Choroi' 'A generic Anime folder should not override credible show text before the bare episode token.'
    $script:RenameTVFilterOptions = Get-NamingRenameTVFilterDefaultOptions
    $script:RenameTVFilterTerms = @{
        services_containers = @('NF', 'AMZN')
        languages_subs_dubs = @('JPN', 'MSubs', 'DUAL')
        release_groups = @('Judas', 'SubsPlease', 'ToonsHub')
    }
    $screenshotTVCases = @(
        [ordered]@{
            Name = '[Judas] Isekai Nonbiri - S02E11.mkv'
            Expected = 'Isekai Nonbiri - S02E11.mkv'
        },
        [ordered]@{
            Name = 'Chainsmoker.Cat.S01E01.1080p.NF.WEB-DL.JPN.AAC2.0.H.264.MSubs-ToonsHub.mkv'
            Expected = 'Chainsmoker Cat - S01E01.mkv'
        },
        [ordered]@{
            Name = 'NIPPON.SANGOKU.The.Three.Nations.of.the.Crimson.Sun.S01E04.The.Seii.Coup.1080p.AMZN.WEB-DL.DUAL.DDP2.0.H.265.MSubs-ToonsHub.mkv'
            Expected = 'NIPPON SANGOKU The Three Nations of the Crimson Sun - S01E04.mkv'
        }
    )
    foreach ($case in $screenshotTVCases) {
        $casePath = Join-Path $genericAnimeRoot ([string]$case.Name)
        [System.IO.File]::WriteAllBytes($casePath, [System.Text.Encoding]::UTF8.GetBytes('screenshot-tv-name'))
        $caseInfo = Get-TVInfoFromFile -file (Get-Item -LiteralPath $casePath) -SourceRootPath $rootTvFolder -LibraryName 'TV' -LibraryId 'tv' -LibraryDesignation 'tv'
        $casePlan = New-PlexDestinationPlan -MediaKind TV -File (Get-Item -LiteralPath $casePath) -TvInfo $caseInfo -OriginalName $caseInfo.OriginalName -Extension 'mkv' -IncludeLibraryFolder
        Assert-True ([bool]$caseInfo.IsReliable) "Screenshot-style accepted workload name '$($case.Name)' must have reliable backend TV identity."
        Assert-Equal $casePlan.FileName ([string]$case.Expected) "Screenshot-style accepted workload name '$($case.Name)' must use the production cleaned filename."
    }
    Remove-Variable -Name RenameTVFilterOptions -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name RenameTVFilterTerms -Scope Script -ErrorAction SilentlyContinue
    Assert-Equal (Get-TVShowNameBeforeBareEpisodeToken -BaseName 'The 100.mkv' -Episode 100) '' 'A title-ending number without a release separator must not be treated as a bare anime episode boundary.'
    Assert-Equal (Get-TVShowNameBeforeBareEpisodeToken -BaseName 'Example Show - 12 Monkeys.mkv' -Episode 12) '' 'A number followed by legitimate title text must not truncate the show at a false bare episode boundary.'

    $namingPreviewScript = Join-Path $repoRoot 'ops\pipeline\entrypoints\Get-NamingPreview.ps1'
    $previewPolicyFingerprint = ('b' * 64)
    $previewTvPath = Join-Path $showFolder 'Example.Show.S02E04 - MoonSource.mkv'
    [System.IO.File]::WriteAllBytes($previewTvPath, [System.Text.Encoding]::UTF8.GetBytes('preview-tv-bytes'))
    $previewV2InputPath = Join-Path $tempRoot 'naming-preview-v2-input.json'
    $previewV2OutputPath = Join-Path $tempRoot 'naming-preview-v2-output.json'
    $previewV2Request = [ordered]@{
        schema_version = 'naming_preview_request.v2'
        rename_cleaning_policy = [ordered]@{
            schema_version = 'rename_cleaning_policy.v1'
            policy_fingerprint = $previewPolicyFingerprint
            movie = [ordered]@{
                options = [ordered]@{
                    video_source = $true
                    audio_channels = $true
                    editions = $true
                    file_size = $true
                    services_containers = $true
                    languages_subs_dubs = $true
                    release_groups = $true
                }
                terms = [ordered]@{
                    release_groups = @('SupaCvnt', 'BYNDR')
                    services_containers = @('MA')
                }
                remove_terms = @('sample', 'trailer')
            }
            tv = [ordered]@{
                options = [ordered]@{
                    video_source = $true
                    audio_channels = $true
                    release_flags = $true
                    services_containers = $true
                    languages_subs_dubs = $true
                    release_groups = $true
                }
                terms = [ordered]@{
                    video_source = @('MoonSource')
                }
                remove_terms = @('UnwantedLeaf')
            }
        }
        items = @(
            [ordered]@{
                path = $previewTvPath
                original_name = [System.IO.Path]::GetFileName($previewTvPath)
                extension = '.mkv'
                media_kind = 'TV'
            }
        )
    }
    $previewV2Request | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $previewV2InputPath -Encoding UTF8
    & $namingPreviewScript -InputJsonPath $previewV2InputPath -OutputJsonPath $previewV2OutputPath
    Assert-True (Test-Path -LiteralPath $previewV2OutputPath -PathType Leaf) 'Naming preview v2 should write its response payload.'
    $previewV2 = Get-Content -LiteralPath $previewV2OutputPath -Raw | ConvertFrom-Json
    Assert-Equal $previewV2.schema_version 'naming_preview.v2' 'Naming preview v2 requests should receive the v2 response contract.'
    Assert-Equal $previewV2.applied_policy_fingerprint $previewPolicyFingerprint 'Naming preview v2 should echo the applied cleaning-policy fingerprint.'
    Assert-Equal @($previewV2.rows).Count 1 'Naming preview v2 should return one row for one request item.'
    Assert-True ([bool]$previewV2.rows[0].ok) ("Naming preview v2 TV row should succeed: " + [string]$previewV2.rows[0].error)
    Assert-Equal $previewV2.rows[0].file_name 'Example Show - S02E04.mkv' 'Naming preview v2 should apply configured TV cleaning terms.'
    Assert-True ($null -ne $previewV2.rows[0].parsed_identity) 'Naming preview v2 rows should include parsed identity evidence.'
    Assert-Equal $previewV2.rows[0].parsed_identity.media_kind 'TV' 'Naming preview v2 parsed identity should identify TV media.'
    Assert-Equal $previewV2.rows[0].parsed_identity.show_name 'Example Show' 'Naming preview v2 parsed identity should expose the parsed show.'
    Assert-Equal $previewV2.rows[0].parsed_identity.show 'Example Show' 'Naming preview v2 parsed identity should expose the canonical show field.'
    Assert-Equal ([int]$previewV2.rows[0].parsed_identity.season) 2 'Naming preview v2 parsed identity should expose the parsed season.'
    Assert-Equal ([int]$previewV2.rows[0].parsed_identity.episode) 4 'Naming preview v2 parsed identity should expose the parsed episode.'
    Assert-Equal ([int]$previewV2.rows[0].parsed_identity.episode_start) 4 'Naming preview v2 parsed identity should expose the canonical starting episode field.'
    Assert-True ([bool]$previewV2.rows[0].parsed_identity.reliable) 'Naming preview v2 parsed identity should expose reliability evidence.'

    $previewV1InputPath = Join-Path $tempRoot 'naming-preview-v1-input.json'
    $previewV1OutputPath = Join-Path $tempRoot 'naming-preview-v1-output.json'
    [ordered]@{
        schema_version = 'naming_preview_request.v1'
        items = @(
            [ordered]@{
                path = $moviePath
                original_name = [System.IO.Path]::GetFileName($moviePath)
                extension = '.mkv'
                media_kind = 'Movie'
            }
        )
    } | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $previewV1InputPath -Encoding UTF8
    & $namingPreviewScript -InputJsonPath $previewV1InputPath -OutputJsonPath $previewV1OutputPath
    Assert-True (Test-Path -LiteralPath $previewV1OutputPath -PathType Leaf) 'Legacy naming preview v1 should still write a response payload.'
    $previewV1 = Get-Content -LiteralPath $previewV1OutputPath -Raw | ConvertFrom-Json
    Assert-Equal $previewV1.schema_version 'naming_preview.v1' 'Legacy naming preview v1 requests should retain the v1 response contract.'
    Assert-True ([bool]$previewV1.rows[0].ok) ("Legacy naming preview v1 row should succeed: " + [string]$previewV1.rows[0].error)
    Assert-Equal $previewV1.rows[0].file_name 'The Matrix (1999).mkv' 'Legacy naming preview v1 should continue using default movie cleaning policy.'

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
