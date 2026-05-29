# ==============================================================================
# engine\naming\naming.ps1
# ==============================================================================
# Movie name cleaning and TV episode parsing / Plex output-name helpers.
# Queue construction and priority-marker functions live in QueuePlan.ps1,
# which MUST be dot-sourced before this module (Naming.ps1 calls
# Remove-PriorityMarkersFromName defined there).
#
# Dot-sourced from MediaPipeline_chatgpt.ps1. Reads at call time:
#   $script:AggressiveEpisodeParsing
#   $script:ValidExtensions
#   $CreateTVSubfolder
#
# Cross-module helpers (loaded before this module):
#   Write-Log
#   Remove-PriorityMarkersFromName  (QueuePlan.ps1)
#
# Functions exported:
#   Normalize-MovieName
#   ConvertTo-MediaPipelineMovieTitleCase
#   Get-CleanMovieName
#   Normalize-TVShowFolderName
#   Get-TVEpisodeFromFilename
#   Resolve-OrdinalSeason
#   Get-TVFolderSeasonInfo
#   Test-TVSpecialSeasonFolderName
#   Get-TVEpisodeFromStrippedName
#   Get-TVLooseParseText
#   Get-TVLooseSeasonEpisodeFromName
#   Get-TVLooseBareEpisodeNumber
#   Get-TVShowNameBeforeSeasonEpisodeTokens
#   Test-TVFolderEpisodeSequenceSupportsCandidate
#   Get-TVAggressiveEpisodeFromName
#   Get-TVInfoFromFile
#   Get-EpisodeTitle
#   Get-CleanTVOutputNamePart
#   Get-CleanTVEpisodeTitle
#   Get-TVInfoField
#   Join-PlexRelativePathParts
#   New-PlexMovieDestinationPlan
#   New-PlexTVDestinationPlan
#   New-PlexDestinationPlan
#   Get-CleanTVFilename
#   Get-TVParseRenameSuggestion
# ==============================================================================
function Normalize-MovieName {
    param([string]$name)
    # FIX#8: The old Normalize-MovieName used a different cleaning pipeline
    # than Get-CleanMovieName (different tag lists, different bracket
    # handling, different case rules). As a result, Build-ProcessedIndex
    # keys computed via Normalize-MovieName never matched the actual
    # Outsource folder names (which are produced by Get-CleanMovieName),
    # and every movie was re-checked on disk for reprocess decisions.
    # Making this a thin wrapper gives us ONE canonical form everywhere.
    #
    # We lowercase the final form so the index hashtable is robust to
    # case differences between the source filename and the folder name.
    $clean = Get-CleanMovieName $name
    return $clean.ToLowerInvariant()
}

function ConvertTo-MediaPipelineMovieTitleCase {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) { return "" }

    $smallWords = @('a','an','and','as','at','but','by','for','from','in','into','nor','of','on','or','per','to','vs','via','with')
    $lowerTheAfter = @('by','for','from','in','into','of','on','to','with')
    $romanNumerals = @('i','ii','iii','iv','v','vi','vii','viii','ix','x')
    $tokens = New-Object System.Collections.Generic.List[string]
    $rawTokens = @($Value -split '\s+' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $previousLower = ''

    for ($i = 0; $i -lt $rawTokens.Count; $i++) {
        $word = [string]$rawTokens[$i]
        if ($word -ceq $word.ToUpperInvariant()) {
            $word = $word.ToLowerInvariant()
        }
        $lower = $word.ToLowerInvariant()
        if ($romanNumerals.Contains($lower)) {
            $formatted = $lower.ToUpperInvariant()
        } elseif ($lower -eq 'the') {
            if (($i -gt 0) -and $lowerTheAfter.Contains($previousLower)) {
                $formatted = 'the'
            } else {
                $formatted = 'The'
            }
        } elseif (($i -gt 0) -and $smallWords.Contains($lower)) {
            $formatted = $lower
        } elseif ($word.Contains('-')) {
            $parts = foreach ($part in $word.Split('-')) {
                if ($part.Length -eq 0) { $part } else { $part.Substring(0,1).ToUpperInvariant() + $part.Substring(1) }
            }
            $formatted = ($parts -join '-')
        } else {
            $formatted = if ($word.Length -eq 0) { $word } else { $word.Substring(0,1).ToUpperInvariant() + $word.Substring(1) }
        }
        [void]$tokens.Add($formatted)
        $previousLower = $formatted.ToLowerInvariant()
    }

    return ($tokens -join ' ')
}

function Get-CleanMovieName {
    param([string]$FileName)

    $base = Remove-PriorityMarkersFromName ([System.IO.Path]::GetFileNameWithoutExtension($FileName))

    # Year detection. Prefer a year that appears inside () or [] brackets,
    # because some titles contain 4-digit numbers that look like years
    # ("Blade Runner 2049"). Fall back to the first unbracketed 4-digit
    # year only when no bracketed year exists.
    $year = ''
    if ($base -match '[\(\[](19|20)(\d{2})[\)\]]') {
        $year = $Matches[1] + $Matches[2]
    } elseif ($base -match '\b(19|20)\d{2}\b') {
        $year = $Matches[0]
    }

    # Strip ALL bracketed groups: (...), [...], {...}. Per user spec, any
    # text inside these is noise we don't want in the folder name (extended
    # cuts, quality tags, release-group markers, etc).
    #
    # We run these in a loop to catch nested cases like "{a{b}c}" — the
    # inner group strips on pass 1, the outer on pass 2. Five passes is
    # vastly more than enough for any real-world filename.
    $title = $base
    for ($bpass = 0; $bpass -lt 5; $bpass++) {
        $before = $title
        $title = $title -replace '\([^()]*\)', ' '
        $title = $title -replace '\[[^\[\]]*\]', ' '
        $title = $title -replace '\{[^{}]*\}', ' '
        if ($title -eq $before) { break }
    }

    # Belt-and-suspenders: if any bracket character is still present
    # (unmatched open brace, unclosed bracket, etc.), strip it. This catches
    # filenames like "Movie {unclosed 2020.mkv" where the open brace has no
    # matching close, and "Movie {a{b}c}" where the outer pair was broken
    # up by the nested inner pair.
    $title = $title -replace '[{}\[\]()]', ' '

    # Release-tag vocabulary that frequently appears unbracketed in scene
    # filenames. Keep this aligned with the desktop rename scrubber so the
    # Rename tab's predictive movie name matches the eventual Plex path.
    $title = $title -replace '\b\d+(?:\.\d+)?\s*(?:mb|gb)\b', ' '
    $title = $title -replace '\b(?:truehd|atmos|flac|opus|eac3|ac3|aac|ddp?|dts(?:[\s._-]*hd)?|dtshd)(?:[\s._-]*(?:1\.0|2\.0|5\.1|7\.1|6ch|8ch))?\b|\b(?:1\.0|2\.0|5\.1|7\.1|6\s*ch|8\s*ch)\b', ' '
    $title = $title -replace '\b(?:2160p|1080p|720p|480p|uhd|hdr|hdr10\+?|dv|dovi|dolby[\s._-]*vision|hevc|h\.?264|h\.?265|x264|x265|av1|avc|blu[\s._-]*ray|brrip|bdrip|webrip|web[\s._-]*dl|webdl|web|hdtv|dvdrip|dvd|remux|imax|proper|repack|rerip|extended|remastered|remaster|unrated|theatrical|criterion|directors?[\s._-]*cut|final[\s._-]*cut|open[\s._-]*matte|amzn|nf|dsnp|hmax|hulu|itunes|appletv|mkv|mp4|m4v)\b', ' '
    $title = $title -replace '\b(?:10|8)\s*bit\b', ' '

    foreach ($group in @('rarbg','rbg','yify','yts','yts lt','galaxyrg','bone','psa','tigole','kris')) {
        $groupPattern = [regex]::Escape($group) -replace '\\ ', '[\s._-]*'
        $title = $title -replace "(?i)^\s*[\[\(]?\s*$groupPattern\s*[\]\)]?[\s._-]+", ' '
        $title = $title -replace "(?i)[\s._-]+[\[\(]?\s*$groupPattern\s*[\]\)]?\s*$", ' '
    }

    # Convert separators (dots, underscores, hyphens-between-words) to spaces.
    # We handle hyphens carefully: "Spider-Man" should keep the hyphen,
    # but "Title - Subtitle - 2024" should lose them. Our rule: a hyphen
    # surrounded by spaces acts as a separator, a hyphen inside a word
    # (flanked by letters on both sides) is preserved.
    $title = $title -replace '[\._]', ' '
    $title = $title -replace '\s-\s', ' '      # " - " as separator
    $title = $title -replace '\s-|-\s',  ' '   # dangling hyphens

    # Drop the year NOW (after bracket stripping) so it isn't duplicated
    # once we reappend "(YYYY)" at the end. Only drop the year if it
    # wasn't bracketed — otherwise the bracketed year is already gone and
    # any remaining 4-digit number is part of the title (e.g. "2049").
    if ($year -and $base -notmatch '[\(\[](19|20)\d{2}[\)\]]') {
        $title = $title -replace "\b$year\b", ' '
    }

    # Collapse whitespace and strip non-filename-safe characters.
    # Preserves letters, digits, spaces, hyphens (for Spider-Man), apostrophes,
    # ampersands, commas, and exclamation marks. Filesystem-hostile chars
    # (<>:"/\|?*) are removed.
    $title = $title -replace '[<>:"/\\|?*]', ''
    $title = ($title -replace '\s+', ' ').Trim()

    $title = ConvertTo-MediaPipelineMovieTitleCase $title

    if ([string]::IsNullOrWhiteSpace($title)) {
        # Fallback: raw base, sanitised, so we never return an empty string.
        $title = ($base -replace '[<>:"/\\|?*]','').Trim()
    }

    if ($year) { return "$title ($year)" }
    return $title
}

function Normalize-TVShowFolderName {
    param([string]$Name)

    if ([string]::IsNullOrWhiteSpace($Name)) { return "" }

    $show = Remove-PriorityMarkersFromName $Name
    $show = $show -replace '\s*\((?:Season\s*)?S?\d{1,2}\)\s*$', ''   # trailing (Season 2) / (S02)
    $show = $show -replace '(?i)\s+Season\s*\d{1,2}\s*$', ''           # trailing "Season 2"
    $show = $show -replace '\s+S\d{1,2}\s*$', ''                       # trailing bare "S02"
    $show = $show -replace '_TV_| TV', ''
    $show = $show -replace '[\._]', ' '
    $show = $show -replace '\s+', ' '
    return $show.Trim()
}

function Get-TVEpisodeFromFilename {
    param([string]$FileName)

    $base = Remove-PriorityMarkersFromName ([System.IO.Path]::GetFileNameWithoutExtension($FileName))
    foreach ($pattern in @(
            '(?i)\bEpisode[\s._-]*(\d{1,3})\b',
            '(?i)\bEp[\s._-]*(\d{1,3})\b',
            '(?i)(?<![A-Za-z0-9])E(\d{1,3})(?![A-Za-z0-9])'
        )) {
        if ($base -match $pattern) {
            return [int]$Matches[1]
        }
    }
    return $null
}

function Resolve-OrdinalSeason {
    # Returns the numeric season from strings containing an ordinal or word-form
    # season marker: "3rd Season" → 3, "Season Three" → 3, "2nd Cour" → 2.
    # Returns $null when no recognised pattern is found.
    param([string]$Text)
    $wordOrdinals = [ordered]@{
        'first'=1; 'second'=2; 'third'=3; 'fourth'=4; 'fifth'=5
        'sixth'=6; 'seventh'=7; 'eighth'=8; 'ninth'=9; 'tenth'=10
    }
    # Numeric ordinal suffix: "3rd Season", "2nd Cour"
    if ($Text -match '(?i)\b(\d+)(?:st|nd|rd|th)\s+(?:Season|Cour)\b') {
        return [int]$Matches[1]
    }
    $wordPat = ($wordOrdinals.Keys -join '|')
    # "Season Three" / "Cour Two"
    if ($Text -match "(?i)\b(?:Season|Cour)\s+($wordPat)\b") {
        return [int]$wordOrdinals[$Matches[1].ToLower()]
    }
    # "Third Season" / "Third Cour"
    if ($Text -match "(?i)\b($wordPat)\s+(?:Season|Cour)\b") {
        return [int]$wordOrdinals[$Matches[1].ToLower()]
    }
    return $null
}

function Test-TVSpecialSeasonFolderName {
    param([string]$Name)

    if ([string]::IsNullOrWhiteSpace($Name)) { return $false }
    return ($Name -match '^(?i)\s*(?:specials?|ovas?|oads?|oavs?|onas?|extras?|bonus|featurettes?|behind[\s._-]*(?:the[\s._-]*)?scenes|deleted[\s._-]*scenes|interviews?|shorts?|trailers?|clips?|promos?|samples?|bts)\s*$')
}

function Get-TVFolderSeasonInfo {
    param([string]$DirectoryPath)

    $current = $DirectoryPath
    for ($depth = 0; $depth -lt 4 -and $current; $depth++) {
        $leaf = Remove-PriorityMarkersFromName (Split-Path $current -Leaf)
        if (-not $leaf) { break }
        $flexibleLeaf = $leaf
        for ($fpass = 0; $fpass -lt 5; $fpass++) {
            $beforeFlexible = $flexibleLeaf
            $flexibleLeaf = $flexibleLeaf -replace '\[[^\[\]]*\]', ' '
            $flexibleLeaf = $flexibleLeaf -replace '\{[^{}]*\}', ' '
            $flexibleLeaf = $flexibleLeaf -replace '(?i)\([^)]*(?:2160p|1080p|720p|480p|uhd|hdr|hevc|h264|h265|x264|x265|av1|bd|blu[\s._-]*ray|web[\s._-]*dl|webdl|webrip|subs?|dual[\s._-]*audio)[^)]*\)', ' '
            if ($flexibleLeaf -eq $beforeFlexible) { break }
        }
        $flexibleLeaf = $flexibleLeaf -replace '[._]+', ' '
        $flexibleLeaf = (($flexibleLeaf -replace '\s+', ' ').Trim(' .-_'))

        if (Test-TVSpecialSeasonFolderName $leaf) {
            $parentLeaf = Split-Path (Split-Path $current -Parent) -Leaf
            return @{
                Season   = 0
                ShowName = (Normalize-TVShowFolderName $parentLeaf)
                Source   = 'specials-folder'
            }
        }
        if ($flexibleLeaf -match '^(?i)\s*Season[\s._-]*(\d{1,2})\s*$') {
            $parentLeaf = Split-Path (Split-Path $current -Parent) -Leaf
            return @{
                Season   = [int]$Matches[1]
                ShowName = (Normalize-TVShowFolderName $parentLeaf)
                Source   = 'season-folder'
            }
        }
        if ($flexibleLeaf -match '^(?i)\s*S[\s._-]*(\d{1,2})\s*$') {
            $parentLeaf = Split-Path (Split-Path $current -Parent) -Leaf
            return @{
                Season   = [int]$Matches[1]
                ShowName = (Normalize-TVShowFolderName $parentLeaf)
                Source   = 's-folder'
            }
        }
        if ($leaf -match '^(?i)(?<show>.+?)\s*\((?:Season\s*)?S?(?<season>\d{1,2})\)\s*$') {
            return @{
                Season   = [int]$Matches['season']
                ShowName = (Normalize-TVShowFolderName $Matches['show'])
                Source   = 'show-folder-suffix'
            }
        }
        if ($flexibleLeaf -match '^(?i)(?<show>.+?)\s+S(?<season>\d{1,2})\s*$') {
            return @{
                Season   = [int]$Matches['season']
                ShowName = (Normalize-TVShowFolderName $Matches['show'])
                Source   = 'show-s-folder'
            }
        }
        if ($flexibleLeaf -match '^(?i)(?<show>.+?)\s*(?:[-–]\s*)?(?:Season|S)[\s._-]*(?<season>\d{1,2})(?!\d)(?:\s+.*)?$') {
            return @{
                Season   = [int]$Matches['season']
                ShowName = (Normalize-TVShowFolderName $Matches['show'])
                Source   = 'show-season-folder'
            }
        }
        # Standalone ordinal season folder: "3rd Season/", "Second Season/"
        # The entire leaf resolves to an ordinal+Season token with no show prefix.
        if ($leaf -match '^(?i)(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+(?:st|nd|rd|th))\s+(?:Season|Cour)\s*$') {
            $ordSeason = Resolve-OrdinalSeason $leaf
            if ($null -ne $ordSeason) {
                $parentLeaf = Split-Path (Split-Path $current -Parent) -Leaf
                return @{
                    Season   = $ordSeason
                    ShowName = (Normalize-TVShowFolderName $parentLeaf)
                    Source   = 'ordinal-season-folder'
                }
            }
        }
        # Combined show+ordinal folder: "That Time I Got Reincarnated 3rd Season/"
        # The leaf ends with "<ordinal> Season" and the prefix is the show name.
        if ($flexibleLeaf -match '^(?i)(?<show>.+?)\s*(?:[-–]\s*)?(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+(?:st|nd|rd|th))\s+(?:Season|Cour)(?:\s*(?:complete)\s*)?$') {
            $ordSeason = Resolve-OrdinalSeason $flexibleLeaf
            if ($null -ne $ordSeason) {
                return @{
                    Season   = $ordSeason
                    ShowName = (Normalize-TVShowFolderName $Matches['show'])
                    Source   = 'show-ordinal-season-folder'
                }
            }
        }

        $current = Split-Path $current -Parent
    }

    return $null
}

function Get-TVEpisodeFromStrippedName {
    # Fallback episode extractor for filenames whose episode number is a bare
    # trailing integer after a separator, e.g.:
    #   "[Group] Show 3rd Season - 12 (BD 1080p x265 FLAC)" → 12
    # Strips all bracket groups and common quality/codec tags first, then looks
    # for <separator><1–3 digits><end>. Only fires after stronger patterns fail.
    param([string]$BaseName)
    $s = $BaseName
    for ($i = 0; $i -lt 5; $i++) {
        $before = $s
        $s = $s -replace '\([^()]*\)', ''
        $s = $s -replace '\[[^\[\]]*\]', ''
        $s = $s -replace '\{[^{}]*\}', ''
        if ($s -eq $before) { break }
    }
    # Strip unbracketed quality/codec tokens that could trail after episode number.
    $s = $s -replace '\b(?:2160p|1080p|720p|480p|uhd|hdr|hdr10|hevc|h264|h265|x264|x265|av1|bluray|blu-ray|webrip|web-dl|webdl|remux|bd|dvd|proper|repack|flac|aac|opus|ac3|dts|truehd|eac3|ddp)\b', ' '
    $s = ($s -replace '\s+', ' ').Trim()
    if ($s -match '[\s._-]+(\d{1,3})\s*$') {
        $ep = [int]$Matches[1]
        if ($ep -ge 1 -and $ep -le 500) { return $ep }
    }
    return $null
}

function Get-TVLooseParseText {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) { return "" }
    $s = Remove-PriorityMarkersFromName $Text
    for ($i = 0; $i -lt 5; $i++) {
        $before = $s
        $s = $s -replace '\([^()]*\)', ' '
        $s = $s -replace '\[[^\[\]]*\]', ' '
        $s = $s -replace '\{[^{}]*\}', ' '
        if ($s -eq $before) { break }
    }
    $s = $s -replace '[{}\[\]()]', ' '
    $s = $s -replace '(?i)\b(?:2160p|1080p|720p|480p|uhd|hdr|hdr10|hevc|h264|h265|x264|x265|av1|bluray|blu-ray|webrip|web-dl|webdl|remux|bd|bdrip|dvd|proper|repack|flac|aac|opus|ac3|dts|truehd|eac3|ddp|10bit|8bit)\b', ' '
    $s = $s -replace '[._]+', ' '
    $s = $s -replace '\s*[-]+\s*', ' '
    return (($s -replace '\s+', ' ').Trim())
}

function Get-TVLooseSeasonEpisodeFromName {
    param([string]$BaseName)

    $s = Get-TVLooseParseText $BaseName
    if ([string]::IsNullOrWhiteSpace($s)) { return $null }

    foreach ($pattern in @(
        '(?i)\bS(?<season>\d{1,2})\s+(?:(?:Episode|Ep|E)\s*)?(?<episode>\d{1,3})\b',
        '(?i)\bSeason\s*(?<season>\d{1,2})\s+(?:(?:Episode|Ep|E)\s*)?(?<episode>\d{1,3})\b'
    )) {
        $m = [regex]::Match($s, $pattern)
        if (-not $m.Success) { continue }
        try {
            $season = [int]$m.Groups['season'].Value
            $episode = [int]$m.Groups['episode'].Value
            if ($season -ge 0 -and $season -le 99 -and $episode -ge 1 -and $episode -le 500) {
                return [pscustomobject]@{
                    Season  = $season
                    Episode = $episode
                    Mode    = 'loose-season-episode'
                    Text    = $s
                }
            }
        } catch {}
    }

    return $null
}

function Get-TVLooseBareEpisodeNumber {
    param([string]$BaseName)

    $s = Get-TVLooseParseText $BaseName
    if ([string]::IsNullOrWhiteSpace($s)) { return $null }
    $s = $s -replace '(?i)\b(?:Season|S)\s*\d{1,2}\b', ' '
    # Strip currency amounts (e.g. "$60,000,000,000") and large comma-grouped
    # numbers before scanning for candidates. Without this, a title like
    # "The $60,000,000,000 Man" produces two candidates (1 and 60), breaking
    # the single-unique-number heuristic that identifies the episode number.
    $s = $s -replace '[$£€¥]\s*\d[\d,.]*', ' '
    $s = $s -replace '\b\d{1,3}(?:,\d{3})+\b', ' '
    $s = ($s -replace '\s+', ' ').Trim()
    $matches = [regex]::Matches($s, '(?<!\d)(\d{1,3})(?!\d)')
    $candidates = [System.Collections.Generic.List[int]]::new()
    foreach ($m in $matches) {
        try {
            $n = [int]$m.Groups[1].Value
            if ($n -ge 1 -and $n -le 500) {
                [void]$candidates.Add($n)
            }
        } catch {}
    }

    $unique = @($candidates | Select-Object -Unique)
    if ($unique.Count -eq 1) {
        return [pscustomobject]@{
            Episode = [int]$unique[0]
            Mode    = 'loose-single-number'
            Text    = $s
        }
    }
    return $null
}

function Get-TVShowNameBeforeExplicitEpisodeToken {
    param([string]$BaseName)

    if ([string]::IsNullOrWhiteSpace($BaseName)) { return "" }
    $base = Remove-PriorityMarkersFromName ([System.IO.Path]::GetFileNameWithoutExtension($BaseName))
    $match = [regex]::Match($base, '(?i)^(?<show>.+?)(?<![A-Za-z0-9])(?:Episode|Ep|E)[\s._-]*\d{1,3}(?![A-Za-z0-9])')
    if (-not $match.Success) { return "" }
    $show = Get-CleanTVOutputNamePart $match.Groups['show'].Value
    if ([string]::IsNullOrWhiteSpace($show)) { return "" }
    return $show
}

function Get-TVShowNameBeforeSeasonEpisodeTokens {
    param([string]$BaseName)

    if ([string]::IsNullOrWhiteSpace($BaseName)) { return "" }
    $base = Remove-PriorityMarkersFromName ([System.IO.Path]::GetFileNameWithoutExtension($BaseName))
    $match = [regex]::Match($base, '(?i)^(?<show>.+?)(?<![A-Za-z0-9])(?:Season|S)[\s._-]*\d{1,2}[\s._-]+(?:(?:Episode|Ep|E)[\s._-]*)?\d{1,3}(?![A-Za-z0-9])')
    if (-not $match.Success) { return "" }
    $show = Get-CleanTVOutputNamePart $match.Groups['show'].Value
    if ([string]::IsNullOrWhiteSpace($show)) { return "" }
    return $show
}

function Test-TVFolderEpisodeSequenceSupportsCandidate {
    param(
        $File,
        [int]$Episode
    )

    if ($null -eq $File -or $Episode -lt 1 -or [string]::IsNullOrWhiteSpace($File.DirectoryName)) {
        return $false
    }

    $valid = if ($script:ValidExtensions) { @($script:ValidExtensions) } else { @('.mkv','.mp4','.avi','.mov','.m4v','.ts','.m2ts') }
    $siblings = @(Get-ChildItem -LiteralPath $File.DirectoryName -File -ErrorAction SilentlyContinue |
        Where-Object { $valid -icontains $_.Extension })
    if ($siblings.Count -lt 2) { return $false }

    $numbers = foreach ($sib in $siblings) {
        $n = Get-TVEpisodeFromStrippedName $sib.BaseName
        if ($null -eq $n) {
            $bare = Get-TVLooseBareEpisodeNumber $sib.BaseName
            if ($bare) { $n = [int]$bare.Episode }
        }
        if ($null -ne $n -and [int]$n -ge 1 -and [int]$n -le 500) { [int]$n }
    }
    $distinct = @($numbers | Sort-Object -Unique)
    if ($distinct.Count -lt 2 -or ($distinct -notcontains $Episode)) { return $false }

    $max = [int](($distinct | Measure-Object -Maximum).Maximum)
    return ($max -eq $siblings.Count -or [math]::Abs($max - $siblings.Count) -le 1)
}

function Get-TVAggressiveEpisodeFromName {
    param(
        [string]$BaseName,
        $File = $null
    )

    $episode = Get-TVEpisodeFromFilename $BaseName
    if ($null -ne $episode) {
        return [pscustomobject]@{ Episode = [int]$episode; Mode = 'aggressive-explicit-token' }
    }

    $episode = Get-TVEpisodeFromStrippedName $BaseName
    if ($null -ne $episode) {
        return [pscustomobject]@{ Episode = [int]$episode; Mode = 'aggressive-trailing-number' }
    }

    $bare = Get-TVLooseBareEpisodeNumber $BaseName
    if ($bare) {
        return [pscustomobject]@{ Episode = [int]$bare.Episode; Mode = [string]$bare.Mode }
    }

    return $null
}

function Get-TVInfoFromFile {
    param($file)
    $name     = Remove-PriorityMarkersFromName $file.Name
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($name)
    $folderSeasonInfo = Get-TVFolderSeasonInfo $file.DirectoryName
    # When the immediate folder is a known extras/featurettes container, look
    # one level higher for the show name so we get "Reservation Dogs" instead
    # of "Featurettes" as the show title.
    $extrasContainers = @(
        'Featurettes','Extras','Specials','Bonus','Behind the Scenes',
        'Deleted Scenes','Interviews','Shorts','Trailers','Behind-the-Scenes',
        'BTS','Clips','Promos','Samples','Featurette'
    )
    $immediateLeaf = Split-Path $file.DirectoryName -Leaf
    $showFolder = if ($extrasContainers -icontains $immediateLeaf) {
        Split-Path $file.DirectoryName -Parent
    } else {
        $file.DirectoryName
    }
    $fallbackShow = if ($folderSeasonInfo -and $folderSeasonInfo.ShowName) {
        [string]$folderSeasonInfo.ShowName
    } else {
        Normalize-TVShowFolderName (Split-Path $showFolder -Leaf)
    }
    if (-not $fallbackShow) { $fallbackShow = "Unknown Show" }
    $info = @{
        ShowName     = $fallbackShow
        Season       = 0
        Episode      = 0
        EpisodeEnd   = $null   # set for multi-episode files (S01E01E02 / S01E01-E02)
        OriginalName = $name
        IsReliable   = $false
        ParseError   = $null
        ParseMode    = "ambiguous"
    }
    if ($name -match '[Ss](\d{1,2})[Ee](\d{1,2})') {
        $info.Season  = [int]$Matches[1]; $info.Episode = [int]$Matches[2]
        # Multi-episode: S01E01E02 or S01E01-E02 or S01E01_E02
        if ($name -match '[Ss]\d{1,2}[Ee]\d{1,2}[-_]?[Ee](\d{1,2})') {
            $epEnd = [int]$Matches[1]
            if ($epEnd -gt $info.Episode) { $info.EpisodeEnd = $epEnd }
        }
        # Extract show name from the portion before the SxxExx marker.
        # ② Preserve 4-digit years like "(2024)" — save before stripping all brackets.
        $showRaw = ($name -replace '[Ss]\d{1,2}[Ee]\d{1,2}.*$','') -replace '[\._]',' '
        $yearTag = if ($showRaw -match '\((\d{4})\)') { " ($($Matches[1]))" } else { '' }
        $show = ($showRaw -replace '\[.*?\]|\(.*?\)','') -replace '\s+',' '
        $show = ($show -replace '[\s\-–_]+$','').Trim()   # ① strip trailing separators
        if ($yearTag) { $show = $show + $yearTag }
        if ($show) {
            $info.ShowName = $show
        } elseif ($folderSeasonInfo -and $folderSeasonInfo.ShowName) {
            $info.ShowName = [string]$folderSeasonInfo.ShowName
        }
        $info.IsReliable = $true
        $info.ParseMode  = if ($info.EpisodeEnd) { "sxxexx-multi" } else { "sxxexx" }
        return $info
    }
    if ($name -match '(?i)(?<!\d)(\d{1,2})x(\d{1,3})(?!\d)') {
        $info.Season  = [int]$Matches[1]; $info.Episode = [int]$Matches[2]
        # ② Preserve year + ① strip trailing separators (same treatment as SxxExx path)
        $showRaw = ($name -replace '(?i)(?<!\d)\d{1,2}x\d{1,3}(?!\d).*$','') -replace '[\._]',' '
        $yearTag = if ($showRaw -match '\((\d{4})\)') { " ($($Matches[1]))" } else { '' }
        $show = ($showRaw -replace '\[.*?\]|\(.*?\)','') -replace '\s+',' '
        $show = ($show -replace '[\s\-–_]+$','').Trim()
        if ($yearTag) { $show = $show + $yearTag }
        if ($show) {
            $info.ShowName = $show
        } elseif ($folderSeasonInfo -and $folderSeasonInfo.ShowName) {
            $info.ShowName = [string]$folderSeasonInfo.ShowName
        }
        $info.IsReliable = $true
        $info.ParseMode  = "nxm"
        return $info
    }

    $filenameSeasonEpisode = Get-TVLooseSeasonEpisodeFromName $baseName
    if ($filenameSeasonEpisode) {
        $info.Season     = [int]$filenameSeasonEpisode.Season
        $info.Episode    = [int]$filenameSeasonEpisode.Episode
        $explicitShow = Get-TVShowNameBeforeSeasonEpisodeTokens $baseName
        if (-not [string]::IsNullOrWhiteSpace($explicitShow)) {
            $info.ShowName = $explicitShow
        } elseif ($folderSeasonInfo -and $folderSeasonInfo.ShowName) {
            $info.ShowName = [string]$folderSeasonInfo.ShowName
        } else {
            $info.ShowName = $fallbackShow
        }
        $info.IsReliable = $true
        $info.ParseMode  = "filename-$($filenameSeasonEpisode.Mode)"
        return $info
    }

    if ($folderSeasonInfo) {
        $info.Season = [int]$folderSeasonInfo.Season
        if ($folderSeasonInfo.ShowName) { $info.ShowName = [string]$folderSeasonInfo.ShowName }

        # ① Try strong episode token first (Episode N / Ep N / E01), then fall
        #   back to Get-TVEpisodeFromStrippedName which catches bare trailing
        #   numbers like "Show 3rd Season - 12 (BD 1080p x265 FLAC)".
        $episode = Get-TVEpisodeFromFilename $name
        $epMode  = 'folder-season+episode-token'
        if ($null -eq $episode) {
            $episode = Get-TVEpisodeFromStrippedName $baseName
            $epMode  = 'folder-season+episode-stripped'
        }
        if ($null -ne $episode) {
            $info.Episode    = [int]$episode
            $explicitShow = Get-TVShowNameBeforeExplicitEpisodeToken $baseName
            if (-not [string]::IsNullOrWhiteSpace($explicitShow)) {
                $info.ShowName = $explicitShow
            }
            $info.IsReliable = $true
            $info.ParseMode  = $epMode
            return $info
        }

        if ($script:AggressiveEpisodeParsing) {
            $looseSeasonEpisode = Get-TVLooseSeasonEpisodeFromName $baseName
            if ($looseSeasonEpisode) {
                $info.Episode    = [int]$looseSeasonEpisode.Episode
                $info.IsReliable = $true
                $info.ParseMode  = "aggressive-folder-season+$($looseSeasonEpisode.Mode)"
                return $info
            }

            $looseEpisode = Get-TVAggressiveEpisodeFromName -BaseName $baseName -File $file
            if ($looseEpisode) {
                $info.Episode    = [int]$looseEpisode.Episode
                $info.IsReliable = $true
                $info.ParseMode  = "aggressive-folder-season+$($looseEpisode.Mode)"
                return $info
            }
        }

        $info.ParseError = "Ambiguous TV filename '$name'. With folder-derived season fallback, rename it to include a strong episode token like Episode 1, Ep 1, or E01."
        return $info
    }

    # ③ Filename begins with "Season N – …", common for featurettes/extras that
    #   lack a season subfolder but embed the season in the name.
    #   "Season 2 - Deleted Scene - Season 2, Episode 3 - Spirit Graffiti" → S02E03
    #   For files with no explicit episode token, use alphabetical position within
    #   the same season's files in the folder as a stable episode number.
    if ($baseName -match '(?i)^Season\s+(\d{1,2})\s*[-–]') {
        $seasonFromPrefix = [int]$Matches[1]
        $episode = Get-TVEpisodeFromFilename $name
        if ($null -eq $episode) { $episode = Get-TVEpisodeFromStrippedName $baseName }
        if ($null -eq $episode) {
            # No explicit episode number — assign alphabetical position within
            # the same season's files in this folder for a deterministic number.
            $sibPattern = "(?i)^Season\s+$seasonFromPrefix\b"
            $sibs = @(Get-ChildItem -LiteralPath $file.DirectoryName -File -ErrorAction SilentlyContinue |
                      Where-Object { $_.Extension -match '\.(mkv|mp4|avi|m4v|ts|mov)$' -and
                                     $_.Name -match $sibPattern } |
                      Sort-Object Name)
            $pos = 1
            for ($si = 0; $si -lt $sibs.Count; $si++) {
                if ($sibs[$si].FullName -eq $file.FullName) { $pos = $si + 1; break }
            }
            $episode = $pos
        }
        $info.Season     = $seasonFromPrefix
        $info.Episode    = [int]$episode
        $info.ShowName   = $fallbackShow
        $info.IsReliable = $true
        $info.ParseMode  = 'filename-season-prefix'
        return $info
    }

    # ② Ordinal season embedded in filename with no season folder above,
    #   e.g. fansub files not placed under a "Season N" or "S0N" subfolder.
    #   Requires an explicit episode token (stripped or strong) to be reliable.
    $ordinalSeason = Resolve-OrdinalSeason $baseName
    if ($null -ne $ordinalSeason) {
        $episode = Get-TVEpisodeFromFilename $name
        if ($null -eq $episode) { $episode = Get-TVEpisodeFromStrippedName $baseName }
        if ($null -ne $episode) {
            $info.Season     = $ordinalSeason
            $info.Episode    = [int]$episode
            $info.IsReliable = $true
            $info.ParseMode  = 'ordinal-season'
            return $info
        }
        # Season resolved but episode unknown — record season so the error
        # message can give a targeted hint.
        $info.Season     = $ordinalSeason
        $info.ParseError = "Ordinal season ($ordinalSeason) found in '$name' but no episode number could be extracted. Add an Episode N, Ep N, E01, or bare trailing number (e.g. '- 03') to the filename."
        return $info
    }

    if ($script:AggressiveEpisodeParsing) {
        $looseSeasonEpisode = Get-TVLooseSeasonEpisodeFromName $baseName
        if ($looseSeasonEpisode) {
            $info.Season     = [int]$looseSeasonEpisode.Season
            $info.Episode    = [int]$looseSeasonEpisode.Episode
            $info.ShowName   = $fallbackShow
            $info.IsReliable = $true
            $info.ParseMode  = "aggressive-$($looseSeasonEpisode.Mode)"
            return $info
        }

        $looseEpisode = Get-TVAggressiveEpisodeFromName -BaseName $baseName -File $file
        $baseLoose = Get-TVLooseParseText $baseName
        $showLoose = Get-TVLooseParseText $fallbackShow
        $looksLikeShowTitleOnly = (
            -not [string]::IsNullOrWhiteSpace($baseLoose) -and
            -not [string]::IsNullOrWhiteSpace($showLoose) -and
            $baseLoose.Equals($showLoose, [System.StringComparison]::OrdinalIgnoreCase)
        )
        if ($looseEpisode -and -not $looksLikeShowTitleOnly) {
            $info.Season     = 1
            $info.Episode    = [int]$looseEpisode.Episode
            $explicitShow = Get-TVShowNameBeforeExplicitEpisodeToken $baseName
            if (-not [string]::IsNullOrWhiteSpace($explicitShow)) {
                $info.ShowName = $explicitShow
            } else {
                $info.ShowName = $fallbackShow
            }
            $info.IsReliable = $true
            $info.ParseMode  = "aggressive-default-season+$($looseEpisode.Mode)"
            return $info
        }
    }

    $info.ShowName = $fallbackShow
    $info.ParseError = "Ambiguous TV filename '$name'. Rename it to include SxxEyy, NxM, or pair a folder season like 'Season 01' / '(S01)' with a filename token like Episode 1, Ep 1, or E01."
    return $info
}

function Get-EpisodeTitle {
    param([string]$name)
    $name = Remove-PriorityMarkersFromName $name
    # ⑤ Fansub-style: "[Group] Show - Episode Title - S01E01 [tags]"
    #    Title sits BEFORE the SxxExx marker, not after it.
    if ($name -match '(?i)-\s+(.+?)\s+-\s+[Ss]\d{1,2}[Ee]\d{1,2}') {
        $candidate = $Matches[1].Trim()
        # Guard: reject if it looks like a raw tag block or is suspiciously long
        if ($candidate -notmatch '^\[' -and $candidate.Length -le 80) {
            return $candidate
        }
    }
    # Standard post-SxxExx title patterns
    if ($name -match '[Ss]\d{1,2}[Ee]\d{1,2}\s*[-]\s*(.+?)(?:\s*[\[\(]|\s*\.\w+$)') { return $Matches[1].Trim() }
    if ($name -match '\d{1,2}x\d{1,2}\s*[-]\s*(.+?)(?:\s*[\[\(]|\s*\.\w+$)')         { return $Matches[1].Trim() }
    if ($name -match 'E\d{2}\s*[-]\s*(.+?)(?:\s*[\[\(]|\s*\.\w+$)')                   { return $Matches[1].Trim() }
    if ($name -match '(?i)Episode\s*\d{1,3}\s*[-]\s*(.+?)(?:\s*[\[\(]|\s*\.\w+$)')   { return $Matches[1].Trim() }
    if ($name -match '(?i)Ep\s*\d{1,3}\s*[-]\s*(.+?)(?:\s*[\[\(]|\s*\.\w+$)')         { return $Matches[1].Trim() }
    $explicitTitle = [regex]::Match($name, '(?i)(?<![A-Za-z0-9])(?:Episode|Ep|E)[\s._-]*\d{1,3}(?![A-Za-z0-9])[\s._-]+(?<title>.+)$')
    if ($explicitTitle.Success) {
        $candidate = $explicitTitle.Groups['title'].Value
        $sourceTag = [regex]::Match($candidate, '(?i)\b(?:2160p|1080p|720p|480p|uhd|hdr10\+?|hdr|dv|dolby[\s._-]*vision|hevc|h\.?264|h\.?265|x264|x265|av1|10\s*bit|8\s*bit|bd|bdrip|blu[\s._-]*ray|bluray|web[\s._-]*dl|webdl|webrip|web|hdtv|dvd|dvdrip|remux|proper|repack|rerip|dual[\s._-]*audio|multi[\s._-]*audio|eng[\s._-]*subs?|multi[\s._-]*subs?|subs?|subbed|dubbed|flac|aac|opus|ac3|eac3|ddp\d*|ddp|dts|truehd|atmos|mkv|mp4)\b')
        if ($sourceTag.Success) {
            $candidate = $candidate.Substring(0, $sourceTag.Index)
        }
        $candidate = $candidate -replace '(?i)\b(?:v\d+|proper|repack|rerip)\b.*$', ' '
        $candidate = ($candidate -replace '\s+', ' ').Trim(' .-_')
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and $candidate.Length -le 80) {
            return $candidate
        }
    }
    return ""
}

function Get-CleanTVOutputNamePart {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) { return "" }

    $clean = Remove-PriorityMarkersFromName ([System.IO.Path]::GetFileNameWithoutExtension($Text))
    $yearToken = 'PLEXYEARTOKEN'
    $yearValue = $null
    if ($clean -match '\((?<year>(?:18|19|20|21)\d{2})\)') {
        $yearValue = $Matches['year']
        $clean = $clean -replace '\((?:18|19|20|21)\d{2}\)', " $yearToken "
    }
    for ($pass = 0; $pass -lt 5; $pass++) {
        $before = $clean
        $clean = $clean -replace '\[[^\[\]]*\]', ' '
        $clean = $clean -replace '\{[^{}]*\}', ' '
        $clean = $clean -replace '(?i)\([^)]*(?:season|specials?|cour|uncensored|censored|2160p|1080p|720p|480p|uhd|hdr|hevc|h264|h265|x264|x265|av1|bd|blu-ray|bluray|web-dl|webdl|webrip|remux|dual\s*audio|multi\s*audio|eng\s*subs?|subs?)[^)]*\)', ' '
        if ($clean -eq $before) { break }
    }

    $clean = $clean -replace '(?i)\bS\d{1,2}E\d{1,3}(?:[-_]?E\d{1,3})?\b', ' '
    $clean = $clean -replace '(?i)\b\d{1,2}x\d{1,3}\b', ' '
    $clean = $clean -replace '(?i)\b(?:season|s)\s*\d{1,2}\s*(?:\+\s*specials?)?\b', ' '
    $clean = $clean -replace '(?i)\b(?:specials?|ova|oav|ona|cour)\b', ' '
    $clean = $clean -replace '(?i)\b(?:uncensored|censored|2160p|1080p|720p|480p|uhd|hdr10\+?|hdr|dv|dolby\s*vision|hevc|h264|h265|x264|x265|av1|10bit|8bit|bd|bdrip|blu-ray|bluray|web-dl|webdl|webrip|web|remux|dvd|proper|repack|dual[-\s]*audio|multi[-\s]*audio|eng[-\s]*subs?|multi[-\s]*subs?|subs?|subbed|dubbed|flac|aac|opus|ac3|eac3|ddp\d*|ddp|dts|truehd|atmos|mkv|mp4)\b', ' '
    $clean = $clean -replace '(?i)\b(?:1\.0|2\.0|5\.1|7\.1|6\s*ch|8\s*ch|6ch|8ch)\b', ' '
    $clean = $clean -replace '(?i)(?:[\s._-]+(?:chotab|subsplease|erai[\s._-]*raws?|judas|ember|bonkai|neohevc|animetime|lostyears|nai|asw|sam|tnp|dedsec|mtbb|smugcat|commie|horriblesubs|kametsu|db|kawaiika|tlacatlc6))+$', ' '
    $clean = $clean -replace '[\[\]{}()]', ' '
    $clean = $clean -replace '[<>:"/\\|?*]', ''
    $clean = $clean -replace '[._]+', ' '
    if ($yearValue) {
        $clean = $clean -replace $yearToken, "($yearValue)"
    }
    $clean = $clean -replace '\s*-\s*$', ''
    $clean = $clean -replace '^\s*-\s*', ''
    return (($clean -replace '\s+', ' ').Trim())
}

function Get-CleanTVEpisodeTitle {
    param([string]$Title)

    $clean = Get-CleanTVOutputNamePart $Title
    if ([string]::IsNullOrWhiteSpace($clean)) { return "" }
    if ($clean.Length -gt 80) { return "" }
    if ($clean -match '(?i)^E\d{1,3}$') { return "" }
    if ($clean -match '(?i)^(?:audio|subs?|subtitles?|dubbed|subbed|english|japanese|bd|hevc|x264|x265)(?:\s+.*)?$') {
        return ""
    }
    return $clean
}

function Get-TVInfoField {
    param(
        $TvInfo,
        [Parameter(Mandatory)] [string]$Name,
        $Default = $null
    )

    if ($null -eq $TvInfo) { return $Default }
    if ($TvInfo -is [System.Collections.IDictionary] -and $TvInfo.Contains($Name)) {
        return $TvInfo[$Name]
    }

    $prop = $TvInfo.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $Default
}

function Join-PlexRelativePathParts {
    param([string[]]$Parts)

    $cleanParts = @($Parts | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($cleanParts.Count -eq 0) { return "" }

    $path = [string]$cleanParts[0]
    for ($i = 1; $i -lt $cleanParts.Count; $i++) {
        $path = Join-Path $path ([string]$cleanParts[$i])
    }
    return $path
}

function Get-RenameOverrideSidecarPath {
    param([Parameter(Mandatory)] $File)

    $fullName = ''
    if ($File -and $File.PSObject.Properties['FullName']) {
        $fullName = [string]$File.FullName
    } else {
        $fullName = [string]$File
    }
    if ([string]::IsNullOrWhiteSpace($fullName)) { return '' }

    $dir = [System.IO.Path]::GetDirectoryName($fullName)
    $base = [System.IO.Path]::GetFileNameWithoutExtension($fullName)
    if ([string]::IsNullOrWhiteSpace($dir) -or [string]::IsNullOrWhiteSpace($base)) { return '' }
    return (Join-Path $dir ($base + '.mediapipeline.rename.json'))
}

function Get-RenameOverrideFinalName {
    param(
        [Parameter(Mandatory)] $File,
        [string]$Extension = ''
    )

    $sidecarPath = Get-RenameOverrideSidecarPath -File $File
    if ([string]::IsNullOrWhiteSpace($sidecarPath) -or -not (Test-Path -LiteralPath $sidecarPath -ErrorAction SilentlyContinue)) {
        return $null
    }

    try {
        $json = Get-Content -LiteralPath $sidecarPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $renameTool = $json.PSObject.Properties['RenameTool']
        if (-not $renameTool) { return $null }
        $payload = $renameTool.Value
        $forceProp = $payload.PSObject.Properties['ForcePipelineName']
        if (-not $forceProp -or -not [bool]$forceProp.Value) { return $null }
        $finalName = [string]$payload.FinalName
        if ([string]::IsNullOrWhiteSpace($finalName)) { return $null }
        $leaf = Split-Path -Leaf $finalName
        $base = [System.IO.Path]::GetFileNameWithoutExtension($leaf)
        if ([string]::IsNullOrWhiteSpace($base)) { return $null }
        $base = ($base -replace '[<>:"/\\|?*]', '' -replace '\s+', ' ').Trim()
        if ([string]::IsNullOrWhiteSpace($base)) { return $null }
        if (-not [string]::IsNullOrWhiteSpace($Extension) -and -not $Extension.StartsWith('.')) {
            $Extension = ".$Extension"
        }
        if ([string]::IsNullOrWhiteSpace($Extension)) {
            $Extension = [System.IO.Path]::GetExtension($leaf)
        }
        return [pscustomobject]@{
            SidecarPath = $sidecarPath
            FileBaseName = $base
            FileName = "$base$Extension"
        }
    } catch {
        if (Get-Command Write-Log -ErrorAction SilentlyContinue) {
            Write-Log "Rename override sidecar ignored for $sidecarPath : $($_.Exception.Message)" "WARN"
        }
        return $null
    }
}

function Apply-RenameOverrideToDestinationPlan {
    param(
        [Parameter(Mandatory)] $Plan,
        $File = $null,
        [string]$Extension = ''
    )

    if ($null -eq $File) { return $Plan }
    $override = Get-RenameOverrideFinalName -File $File -Extension $Extension
    if ($null -eq $override) { return $Plan }

    $Plan.FileBaseName = [string]$override.FileBaseName
    $Plan.FileName = [string]$override.FileName
    $Plan.SidecarBaseName = [string]$override.FileBaseName
    if ($Plan.PSObject.Properties['MediaKind'] -and [string]$Plan.MediaKind -eq 'Movie') {
        if ($Plan.PSObject.Properties['MovieTitle']) { $Plan.MovieTitle = [string]$override.FileBaseName }
        if ($Plan.PSObject.Properties['FolderName']) { $Plan.FolderName = [string]$override.FileBaseName }
        if ($Plan.PSObject.Properties['LibraryFolder'] -and -not [string]::IsNullOrWhiteSpace([string]$Plan.LibraryFolder)) {
            $Plan.RelativeDirectory = Join-PlexRelativePathParts @([string]$Plan.LibraryFolder, [string]$override.FileBaseName)
        } else {
            $Plan.RelativeDirectory = [string]$override.FileBaseName
        }
        if ($Plan.PSObject.Properties['IdentityKey']) { $Plan.IdentityKey = [string]$override.FileBaseName }
    }
    $Plan.RelativePath = Join-PlexRelativePathParts @([string]$Plan.RelativeDirectory, [string]$Plan.FileName)
    if (-not $Plan.PSObject.Properties['RenameOverrideApplied']) {
        $Plan | Add-Member -NotePropertyName 'RenameOverrideApplied' -NotePropertyValue $true
    } else {
        $Plan.RenameOverrideApplied = $true
    }
    if (-not $Plan.PSObject.Properties['RenameOverrideSidecar']) {
        $Plan | Add-Member -NotePropertyName 'RenameOverrideSidecar' -NotePropertyValue ([string]$override.SidecarPath)
    } else {
        $Plan.RenameOverrideSidecar = [string]$override.SidecarPath
    }
    return $Plan
}

function New-PlexMovieDestinationPlan {
    param(
        [Parameter(Mandatory)] [string]$OriginalName,
        [string]$Extension = "",
        [switch]$IncludeLibraryFolder,
        [string]$LibraryFolder = "Movies"
    )

    $cleanBase = Get-CleanMovieName $OriginalName
    if ([string]::IsNullOrWhiteSpace($cleanBase)) {
        $cleanBase = ([System.IO.Path]::GetFileNameWithoutExtension($OriginalName) -replace '[<>:"/\\|?*]', '').Trim()
    }
    if ([string]::IsNullOrWhiteSpace($cleanBase)) { $cleanBase = 'Unknown Movie' }

    if (-not [string]::IsNullOrWhiteSpace($Extension) -and -not $Extension.StartsWith('.')) {
        $Extension = ".$Extension"
    }
    $fileName = if ($Extension) { "$cleanBase$Extension" } else { $cleanBase }
    $relativeDirectory = if ($IncludeLibraryFolder) {
        Join-PlexRelativePathParts @($LibraryFolder, $cleanBase)
    } else {
        $cleanBase
    }
    $relativePath = if ($fileName) {
        Join-PlexRelativePathParts @($relativeDirectory, $fileName)
    } else {
        $relativeDirectory
    }

    return [pscustomobject]@{
        MediaKind          = 'Movie'
        MovieTitle         = $cleanBase
        FolderName         = $cleanBase
        FileBaseName       = $cleanBase
        FileName           = $fileName
        SidecarBaseName    = $cleanBase
        LibraryFolder      = if ($IncludeLibraryFolder) { $LibraryFolder } else { '' }
        RelativeDirectory  = $relativeDirectory
        RelativePath       = $relativePath
        IdentityKey        = $cleanBase
        SourceOriginalName = $OriginalName
    }
}

function New-PlexTVDestinationPlan {
    param(
        [Parameter(Mandatory)] $TvInfo,
        [string]$OriginalName = "",
        [string]$Extension = "",
        [switch]$IncludeLibraryFolder,
        [string]$LibraryFolder = "TV"
    )

    $rawShow = [string](Get-TVInfoField -TvInfo $TvInfo -Name 'ShowName' -Default '')
    $show = Get-CleanTVOutputNamePart $rawShow
    if ([string]::IsNullOrWhiteSpace($show)) {
        $show = ($rawShow -replace '[<>:"/\\|?*]', '').Trim()
    }
    if ([string]::IsNullOrWhiteSpace($show)) { $show = 'Unknown Show' }

    $season = [int](Get-TVInfoField -TvInfo $TvInfo -Name 'Season' -Default 0)
    $episode = [int](Get-TVInfoField -TvInfo $TvInfo -Name 'Episode' -Default 0)
    $episodeEndValue = Get-TVInfoField -TvInfo $TvInfo -Name 'EpisodeEnd' -Default $null
    $episodeEnd = $null
    if ($null -ne $episodeEndValue -and "$episodeEndValue" -match '^\d+$') {
        $episodeEnd = [int]$episodeEndValue
    }

    $episodeCode = "S$($season.ToString('00'))E$($episode.ToString('00'))"
    if ($episodeEnd -and $episodeEnd -gt $episode) {
        $episodeCode += "-E$($episodeEnd.ToString('00'))"
    }

    $sourceName = if ($OriginalName) {
        $OriginalName
    } else {
        [string](Get-TVInfoField -TvInfo $TvInfo -Name 'OriginalName' -Default '')
    }
    $episodeTitle = Get-CleanTVEpisodeTitle (Get-EpisodeTitle $sourceName)

    $fileBaseName = "$show - $episodeCode"
    if ($episodeTitle) { $fileBaseName += " - $episodeTitle" }
    $fileBaseName = ($fileBaseName -replace '[<>:"/\\|?*]', '' -replace '\s+', ' ').Trim()

    if (-not [string]::IsNullOrWhiteSpace($Extension) -and -not $Extension.StartsWith('.')) {
        $Extension = ".$Extension"
    }
    $fileName = if ($Extension) { "$fileBaseName$Extension" } else { $fileBaseName }
    $seasonFolder = "Season $($season.ToString('00'))"
    $relativeDirectory = if ($IncludeLibraryFolder) {
        Join-PlexRelativePathParts @($LibraryFolder, $show, $seasonFolder)
    } else {
        Join-PlexRelativePathParts @($show, $seasonFolder)
    }
    $relativePath = if ($fileName) {
        Join-PlexRelativePathParts @($relativeDirectory, $fileName)
    } else {
        $relativeDirectory
    }

    return [pscustomobject]@{
        MediaKind         = 'TV'
        ShowTitle         = $show
        SeasonNumber      = $season
        EpisodeNumber     = $episode
        EpisodeEnd        = $episodeEnd
        EpisodeCode       = $episodeCode
        SeasonFolder      = $seasonFolder
        EpisodeTitle      = $episodeTitle
        HasEpisodeTitle   = -not [string]::IsNullOrWhiteSpace($episodeTitle)
        FileBaseName      = $fileBaseName
        FileName          = $fileName
        SidecarBaseName   = $fileBaseName
        LibraryFolder     = if ($IncludeLibraryFolder) { $LibraryFolder } else { '' }
        RelativeDirectory = $relativeDirectory
        RelativePath      = $relativePath
        IdentityKey       = ("{0}_S{1}E{2}" -f $show, $season.ToString('00'), $episode.ToString('00'))
        ParseMode         = [string](Get-TVInfoField -TvInfo $TvInfo -Name 'ParseMode' -Default '')
        SourceOriginalName = $sourceName
    }
}

function New-PlexDestinationPlan {
    param(
        [Parameter(Mandatory)] [ValidateSet('Movie','TV')] [string]$MediaKind,
        $File = $null,
        $TvInfo = $null,
        [string]$OriginalName = "",
        [string]$Extension = "",
        [switch]$IncludeLibraryFolder,
        [string]$LibraryFolder = ""
    )

    if ([string]::IsNullOrWhiteSpace($OriginalName) -and $File -and $File.PSObject.Properties['Name']) {
        $OriginalName = [string]$File.Name
    }

    if ($MediaKind -eq 'TV') {
        if ($null -eq $TvInfo) { throw 'TvInfo is required for TV destination planning.' }
        if ([string]::IsNullOrWhiteSpace($OriginalName)) {
            $OriginalName = [string](Get-TVInfoField -TvInfo $TvInfo -Name 'OriginalName' -Default '')
        }
        $tvLibraryFolder = if ([string]::IsNullOrWhiteSpace($LibraryFolder)) { 'TV' } else { $LibraryFolder }
        $plan = New-PlexTVDestinationPlan `
            -TvInfo $TvInfo `
            -OriginalName $OriginalName `
            -Extension $Extension `
            -IncludeLibraryFolder:$IncludeLibraryFolder `
            -LibraryFolder $tvLibraryFolder
        return (Apply-RenameOverrideToDestinationPlan -Plan $plan -File $File -Extension $Extension)
    }

    $movieLibraryFolder = if ([string]::IsNullOrWhiteSpace($LibraryFolder)) { 'Movies' } else { $LibraryFolder }
    $plan = New-PlexMovieDestinationPlan `
        -OriginalName $OriginalName `
        -Extension $Extension `
        -IncludeLibraryFolder:$IncludeLibraryFolder `
        -LibraryFolder $movieLibraryFolder
    return (Apply-RenameOverrideToDestinationPlan -Plan $plan -File $File -Extension $Extension)
}

function Get-CleanTVFilename {
    param($tvInfo, [string]$origName)
    return (New-PlexTVDestinationPlan -TvInfo $tvInfo -OriginalName $origName).FileBaseName
}

function Get-TVParseRenameSuggestion {
    param($File, $TvInfo)

    $ext = [System.IO.Path]::GetExtension($File.Name)
    if ($TvInfo -and $null -ne $TvInfo.Season -and [int]$TvInfo.Season -ge 0 -and $TvInfo.ShowName) {
        $show = Get-CleanTVOutputNamePart ([string](Get-TVInfoField -TvInfo $TvInfo -Name 'ShowName' -Default ''))
        if ([string]::IsNullOrWhiteSpace($show)) { $show = ([string]$TvInfo.ShowName -replace '[<>:"/\\|?*]', '').Trim() }
        return ("{0} - S{1}E##{2}" -f $show, ([int]$TvInfo.Season).ToString('00'), $ext)
    }
    return "Show Name - S01E01$ext"
}
