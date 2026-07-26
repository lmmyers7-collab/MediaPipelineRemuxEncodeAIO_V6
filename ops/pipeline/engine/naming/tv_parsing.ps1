# ==============================================================================
# ops\pipeline\engine\naming\tv_parsing.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\naming\naming.ps1. Keep function names stable;
# naming.ps1 dot-sources this file as the public compatibility surface.
# ==============================================================================

function Normalize-TVShowFolderName {
    param([string]$Name)

    if ([string]::IsNullOrWhiteSpace($Name)) { return "" }

    $show = Remove-PriorityMarkersFromName $Name
    $show = $show -replace '\s*\((?:Season\s*)?S?\d{1,2}\)\s*$', ''   # trailing (Season 2) / (S02)
    $show = $show -replace '(?i)\s+Season\s*\d{1,2}\s*(?:\+\s*(?:sp|specials?))?(?:\s+.*)?$', ''
    $show = $show -replace '(?i)\s+S\d{1,2}\s*(?:\+\s*(?:sp|specials?))?(?:\s+.*)?$', ''
    # `_TV_` is a historical structural separator. A lexical "TV" token is
    # authoritative title text (for example, "The TV Set") and must survive.
    $show = $show -replace '_TV_', ' '
    $show = $show -replace '[\._]', ' '
    $show = $show -replace '\s+', ' '
    return $show.Trim()
}

function Get-TVEpisodeFromFilename {
    param([string]$FileName)

    $base = Remove-PriorityMarkersFromName ([System.IO.Path]::GetFileNameWithoutExtension($FileName))
    foreach ($pattern in @(
            '(?i)\bEpisode[\s._-]*(\d{1,3})(?:v\d+)?\b',
            '(?i)\bEp[\s._-]*(\d{1,3})(?:v\d+)?\b',
            '(?i)(?<![A-Za-z0-9])E(\d{1,3})(?:v\d+)?(?![A-Za-z0-9])'
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
        $flexibleLeaf = $flexibleLeaf -replace '(?i)\b(S\d{1,2})\s*\+\s*(?:sp|specials?)\b', '$1 '
        $flexibleLeaf = $flexibleLeaf -replace '(?i)\b(Season\s*\d{1,2})\s*\+\s*(?:sp|specials?)\b', '$1 '
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
        if ($flexibleLeaf -match '^(?i)(?<show>.+?)\s+S(?<season>\d{1,2})(?!\d)(?:\s*\+\s*(?:sp|specials?)\b)?\s*$') {
            return @{
                Season   = [int]$Matches['season']
                ShowName = (Normalize-TVShowFolderName $Matches['show'])
                Source   = 'show-s-folder'
            }
        }
        if ($flexibleLeaf -match '^(?i)(?<show>.+?)\s*(?:[-–]\s*)?(?:Season|S)[\s._-]*(?<season>\d{1,2})(?!\d)(?:\s*\+\s*(?:sp|specials?)\b)?(?:\s+.*)?$') {
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
    if ($s -match '(?i)[\s._-]+(\d{1,3})(?:v\d+)?\s*$') {
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
    $s = $s -replace '(?i)\b(?:2160p|1080p|720p|480p|uhd|hdr|hdr10|hevc|h264|h265|x264|x265|av1|bluray|blu-ray|webrip|web-dl|webdl|remux|bd|bdrip|dvd|proper|repack|flac|aac|opus|ac3|dts|truehd|eac3|ddp|10[\s._-]*bits?|8[\s._-]*bits?|upscale(?:d)?)\b', ' '
    $s = $s -replace '[._]+', ' '
    $s = $s -replace '\s*[-]+\s*', ' '
    return (($s -replace '\s+', ' ').Trim())
}

function Get-TVLooseSeasonEpisodeFromName {
    param([string]$BaseName)

    $s = Get-TVLooseParseText $BaseName
    if ([string]::IsNullOrWhiteSpace($s)) { return $null }

    foreach ($pattern in @(
        '(?i)\bS(?<season>\d{1,2})\s+(?:(?:Episode|Ep|E)\s*)?(?<episode>\d{1,3})(?:v\d+)?\b',
        '(?i)\bSeason\s*(?<season>\d{1,2})\s+(?:(?:Episode|Ep|E)\s*)?(?<episode>\d{1,3})(?:v\d+)?\b'
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
    $matches = [regex]::Matches($s, '(?i)(?<!\d)(\d{1,3})(?:v\d+)?(?![A-Za-z0-9])')
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
    $match = [regex]::Match($base, '(?i)^(?<show>.+?)(?<![A-Za-z0-9])(?:Episode|Ep|E)[\s._-]*\d{1,3}(?:v\d+)?(?![A-Za-z0-9])')
    if (-not $match.Success) { return "" }
    $show = Get-CleanTVOutputNamePart -Text $match.Groups['show'].Value -PreserveTitleTerms
    if ([string]::IsNullOrWhiteSpace($show)) { return "" }
    return $show
}

function Get-TVShowNameBeforeBareEpisodeToken {
    param(
        [string]$BaseName,
        [int]$Episode
    )

    if ([string]::IsNullOrWhiteSpace($BaseName) -or $Episode -lt 1 -or $Episode -gt 999) { return "" }
    $base = Remove-PriorityMarkersFromName ([System.IO.Path]::GetFileNameWithoutExtension($BaseName))
    # Bare anime episodes are credible for show extraction only with a clear
    # release separator and with the token followed by metadata or end-of-name.
    # This rejects title numbers such as "The 100" and "Show - 12 Monkeys".
    $match = [regex]::Match($base, '(?i)^(?<show>.+?)\s+-\s*(?<episode>\d{1,3})(?:v\d+)?(?=\s*(?:[\(\[\{]|$))')
    if (-not $match.Success -or [int]$match.Groups['episode'].Value -ne $Episode) { return "" }
    $show = Get-CleanTVOutputNamePart -Text $match.Groups['show'].Value -PreserveTitleTerms
    if ([string]::IsNullOrWhiteSpace($show)) { return "" }
    return $show
}

function Get-TVShowNameBeforeSpecialMarker {
    param([string]$BaseName)

    if ([string]::IsNullOrWhiteSpace($BaseName)) { return "" }
    $base = Remove-PriorityMarkersFromName ([System.IO.Path]::GetFileNameWithoutExtension($BaseName))
    $match = [regex]::Match($base, '(?i)^(?<show>.+?)(?<![A-Za-z0-9])(?:OVA|OAV|ONA|Specials?)(?=$|[\s._-])')
    if (-not $match.Success) { return "" }
    $show = Get-CleanTVOutputNamePart -Text $match.Groups['show'].Value -PreserveTitleTerms
    if ([string]::IsNullOrWhiteSpace($show)) { return "" }
    return $show
}

function Get-TVShowNameBeforeSeasonEpisodeTokens {
    param([string]$BaseName)

    if ([string]::IsNullOrWhiteSpace($BaseName)) { return "" }
    $base = Remove-PriorityMarkersFromName ([System.IO.Path]::GetFileNameWithoutExtension($BaseName))
    $match = [regex]::Match($base, '(?i)^(?<show>.+?)(?<![A-Za-z0-9])(?:Season|S)[\s._-]*\d{1,2}[\s._-]+(?:(?:Episode|Ep|E)[\s._-]*)?\d{1,3}(?:v\d+)?(?![A-Za-z0-9])')
    if (-not $match.Success) { return "" }
    $show = Get-CleanTVOutputNamePart -Text $match.Groups['show'].Value -PreserveTitleTerms
    if ([string]::IsNullOrWhiteSpace($show)) { return "" }
    return $show
}

function Get-TVShowNameBeforeOrdinalSeasonToken {
    param([string]$BaseName)

    if ([string]::IsNullOrWhiteSpace($BaseName)) { return "" }
    $base = Remove-PriorityMarkersFromName ([System.IO.Path]::GetFileNameWithoutExtension($BaseName))
    $wordPat = 'first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+(?:st|nd|rd|th)'
    $pattern = '(?i)^(?<show>.+?)(?<![A-Za-z0-9])(?:' + $wordPat + ')\s+(?:Season|Cour)\b'
    $match = [regex]::Match($base, $pattern)
    if (-not $match.Success) { return "" }
    $show = Get-CleanTVOutputNamePart -Text $match.Groups['show'].Value -PreserveTitleTerms
    if ([string]::IsNullOrWhiteSpace($show)) { return "" }
    return $show
}

function Get-TVShowNameComparisonKey {
    param([string]$Name)

    if ([string]::IsNullOrWhiteSpace($Name)) { return "" }
    $clean = Get-CleanTVOutputNamePart -Text $Name -PreserveTitleTerms
    if ([string]::IsNullOrWhiteSpace($clean)) {
        $clean = Remove-PriorityMarkersFromName $Name
    }
    $clean = $clean -replace '(?i)\blibrary\b', ' '
    $clean = $clean -replace '[^A-Za-z0-9]+', ' '
    $clean = ($clean -replace '\s+', ' ').Trim().ToLowerInvariant()
    return $clean
}

function Add-TVDisallowedShowNameLabel {
    param(
        [hashtable]$Keys,
        [string]$Label
    )

    if ($null -eq $Keys -or [string]::IsNullOrWhiteSpace($Label)) { return }
    foreach ($candidate in @($Label, ($Label -replace '(?i)\blibrary\b', ' '))) {
        $key = Get-TVShowNameComparisonKey $candidate
        if (-not [string]::IsNullOrWhiteSpace($key)) {
            $Keys[$key] = $true
        }
    }
}

function Get-TVDisallowedLibraryFallbackShowNameKeys {
    param(
        [string]$SourceRootPath = '',
        [string]$LibraryName = '',
        [string]$LibraryId = '',
        [string]$LibraryDesignation = ''
    )

    $keys = @{}
    foreach ($label in @('TV', 'Television', 'TV Shows', 'Shows', 'Series')) {
        Add-TVDisallowedShowNameLabel -Keys $keys -Label $label
    }

    $isTvLibrary = [string]::Equals($LibraryDesignation, 'tv', [System.StringComparison]::OrdinalIgnoreCase)
    if ($isTvLibrary -or -not [string]::IsNullOrWhiteSpace($SourceRootPath)) {
        Add-TVDisallowedShowNameLabel -Keys $keys -Label $LibraryName
        Add-TVDisallowedShowNameLabel -Keys $keys -Label $LibraryId
        if (-not [string]::IsNullOrWhiteSpace($SourceRootPath)) {
            Add-TVDisallowedShowNameLabel -Keys $keys -Label (Split-Path $SourceRootPath -Leaf)
        }
    }
    return $keys
}

function Test-TVShowNameMatchesDisallowedLibraryFallback {
    param(
        [string]$ShowName,
        [hashtable]$DisallowedShowNameKeys
    )

    if ([string]::IsNullOrWhiteSpace($ShowName) -or $null -eq $DisallowedShowNameKeys) { return $false }
    $key = Get-TVShowNameComparisonKey $ShowName
    return (-not [string]::IsNullOrWhiteSpace($key) -and $DisallowedShowNameKeys.ContainsKey($key))
}

function Set-TVInfoLibraryFallbackParseError {
    param(
        $Info,
        [string]$OriginalName
    )

    if ($null -eq $Info) { return $Info }
    $showName = [string](Get-TVInfoField -TvInfo $Info -Name 'ShowName' -Default '')
    $Info.IsReliable = $false
    $Info.ParseMode = 'library-fallback-blocked'
    $Info.ParseError = "TV show name resolved to library/root label '$showName' for '$OriginalName'. Put the file under a show folder or include the show title before the season/episode token."
    return $Info
}

function Confirm-TVInfoShowNameAllowed {
    param(
        $Info,
        [hashtable]$DisallowedShowNameKeys,
        [string]$OriginalName
    )

    if ($Info -and $Info.IsReliable -and (
        [int]$Info.Season -lt 0 -or [int]$Info.Season -gt 99 -or
        [int]$Info.Episode -lt 1 -or [int]$Info.Episode -gt 999 -or
        ($null -ne $Info.EpisodeEnd -and ([int]$Info.EpisodeEnd -le [int]$Info.Episode -or [int]$Info.EpisodeEnd -gt 999)))) {
        $Info.IsReliable = $false
        $Info.ParseMode = 'identity-out-of-range'
        $Info.ParseError = "Invalid TV identity in '$OriginalName'. Seasons must be 0-99, episodes 1-999, and ranges must increase; use SxxEyy-Ezz."
        return $Info
    }
    if ($Info -and $Info.IsReliable -and (Test-TVShowNameMatchesDisallowedLibraryFallback -ShowName ([string]$Info.ShowName) -DisallowedShowNameKeys $DisallowedShowNameKeys)) {
        return (Set-TVInfoLibraryFallbackParseError -Info $Info -OriginalName $OriginalName)
    }
    if ($Info -and $Info.IsReliable) {
        $Info.EpisodeTitle = Get-CleanTVEpisodeTitle (Get-EpisodeTitle $OriginalName)
        if ($null -eq $Info.Revision -and $OriginalName -match '(?i)(?<![A-Za-z0-9])(?:S\d{1,2}E\d{1,3}(?:(?:E|[-_]E)\d{1,3})?|(?:Episode|Ep|E)[\s._-]*\d{1,3}|\d{1,2}x\d{1,3})v(?<revision>\d+)(?![A-Za-z0-9])') {
            $Info.Revision = [int]$Matches['revision']
        }
        if ($null -eq $Info.Revision -and $OriginalName -match '(?i)(?<![A-Za-z0-9])(?<episode>\d{1,3})v(?<revision>\d+)(?![A-Za-z0-9])' -and [int]$Matches['episode'] -eq [int]$Info.Episode) {
            $Info.Revision = [int]$Matches['revision']
        }
    }
    return $Info
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
    param(
        $file,
        [string]$SourceRootPath = '',
        [string]$LibraryName = '',
        [string]$LibraryId = '',
        [string]$LibraryDesignation = ''
    )
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
    $disallowedShowNameKeys = Get-TVDisallowedLibraryFallbackShowNameKeys -SourceRootPath $SourceRootPath -LibraryName $LibraryName -LibraryId $LibraryId -LibraryDesignation $LibraryDesignation
    $info = @{
        ShowName     = $fallbackShow
        Season       = 0
        Episode      = 0
        EpisodeEnd   = $null   # set for multi-episode files (S01E01E02 / S01E01-E02)
        EpisodeTitle = ''
        Revision     = $null
        OriginalName = $name
        IsReliable   = $false
        ParseError   = $null
        ParseMode    = "ambiguous"
    }
    if ($name -match '(?i)(?<![A-Za-z0-9])S\d{1,3}E\d{1,4}[-_]\d{1,4}(?![A-Za-z0-9])') {
        $info.ParseError = "Noncanonical TV episode range in '$name'. Rename it to use SxxEyy-Ezz."
        $info.ParseMode = 'noncanonical-range'
        return $info
    }
    if ($name -match '(?i)(?<![A-Za-z0-9])(?:Episode|Ep|E)[\s._-]*(?<episode>\d{4,})(?![A-Za-z0-9])') {
        $info.ParseError = "TV identity in '$name' is outside S00-S99 or E001-E999; use SxxEyy or SxxEyy-Ezz."
        $info.ParseMode = 'out-of-range'
        return $info
    }
    $canonicalEpisode = [regex]::Match($name, '(?i)(?<![A-Za-z0-9])S(?<season>\d{1,3})E(?<start>\d{1,4})(?:(?:E|[-_]E)(?<end>\d{1,4}))?(?:v(?<revision>\d+))?(?![A-Za-z0-9])')
    if ($canonicalEpisode.Success) {
        $info.Season = [int]$canonicalEpisode.Groups['season'].Value
        $info.Episode = [int]$canonicalEpisode.Groups['start'].Value
        if ($info.Season -gt 99 -or $info.Episode -lt 1 -or $info.Episode -gt 999) {
            $info.ParseError = "TV identity in '$name' is outside S00-S99 or E001-E999; use SxxEyy or SxxEyy-Ezz."
            $info.ParseMode = 'out-of-range'
            return $info
        }
        if ($canonicalEpisode.Groups['end'].Success) {
            $epEnd = [int]$canonicalEpisode.Groups['end'].Value
            if ($epEnd -lt 1 -or $epEnd -gt 999 -or $epEnd -le $info.Episode) {
                $info.ParseError = "Invalid TV episode range in '$name': the range must increase and remain within E001-E999. Use SxxEyy-Ezz."
                $info.ParseMode = 'invalid-range'
                return $info
            }
            $info.EpisodeEnd = $epEnd
        }
        if ($canonicalEpisode.Groups['revision'].Success) {
            $info.Revision = [int]$canonicalEpisode.Groups['revision'].Value
        }
        # Extract show name from the portion before the SxxExx marker.
        # ② Preserve 4-digit years like "(2024)" — save before stripping all brackets.
        $showRaw = $name.Substring(0, $canonicalEpisode.Index) -replace '[\._]',' '
        $yearTag = if ($showRaw -match '\((\d{4})\)') { " ($($Matches[1]))" } else { '' }
        $show = ($showRaw -replace '\[.*?\]|\(.*?\)','') -replace '\s+',' '
        $show = ($show -replace '[\s\-–_]+$','').Trim()   # ① strip trailing separators
        if ($yearTag) { $show = $show + $yearTag }
        $cleanShow = Get-CleanTVOutputNamePart -Text $show -PreserveTitleTerms
        if (-not [string]::IsNullOrWhiteSpace($cleanShow)) { $show = $cleanShow }
        if ($show) {
            $info.ShowName = $show
        } elseif ($folderSeasonInfo -and $folderSeasonInfo.ShowName) {
            $info.ShowName = [string]$folderSeasonInfo.ShowName
        }
        $info.IsReliable = $true
        $info.ParseMode  = if ($info.EpisodeEnd) { "sxxexx-range" } else { "sxxexx" }
        return (Confirm-TVInfoShowNameAllowed -Info $info -DisallowedShowNameKeys $disallowedShowNameKeys -OriginalName $name)
    }
    if ($name -match '(?i)(?<![A-Za-z0-9])(?:Episode|Ep)[\s._-]*\d{1,3}\s*[-_]\s*(?:E(?:pisode|p)?[\s._-]*)?\d{1,3}(?![A-Za-z0-9])' -or
        $baseName -match '(?i)(?:^|[\s._-])\d{1,3}\s*[-_]\s*\d{1,3}(?:$|[\s._-])') {
        $info.ParseError = "Noncanonical TV episode range in '$name'. Rename it to use SxxEyy-Ezz."
        $info.ParseMode = 'noncanonical-range'
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
        return (Confirm-TVInfoShowNameAllowed -Info $info -DisallowedShowNameKeys $disallowedShowNameKeys -OriginalName $name)
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
        return (Confirm-TVInfoShowNameAllowed -Info $info -DisallowedShowNameKeys $disallowedShowNameKeys -OriginalName $name)
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
            return (Confirm-TVInfoShowNameAllowed -Info $info -DisallowedShowNameKeys $disallowedShowNameKeys -OriginalName $name)
        }

        if ($script:AggressiveEpisodeParsing) {
            $looseSeasonEpisode = Get-TVLooseSeasonEpisodeFromName $baseName
            if ($looseSeasonEpisode) {
                $info.Episode    = [int]$looseSeasonEpisode.Episode
                $info.IsReliable = $true
                $info.ParseMode  = "aggressive-folder-season+$($looseSeasonEpisode.Mode)"
                return (Confirm-TVInfoShowNameAllowed -Info $info -DisallowedShowNameKeys $disallowedShowNameKeys -OriginalName $name)
            }

            $looseEpisode = Get-TVAggressiveEpisodeFromName -BaseName $baseName -File $file
            if ($looseEpisode) {
                $info.Episode    = [int]$looseEpisode.Episode
                $info.IsReliable = $true
                $info.ParseMode  = "aggressive-folder-season+$($looseEpisode.Mode)"
                return (Confirm-TVInfoShowNameAllowed -Info $info -DisallowedShowNameKeys $disallowedShowNameKeys -OriginalName $name)
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
        return (Confirm-TVInfoShowNameAllowed -Info $info -DisallowedShowNameKeys $disallowedShowNameKeys -OriginalName $name)
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
            $explicitShow = Get-TVShowNameBeforeOrdinalSeasonToken $baseName
            if (-not [string]::IsNullOrWhiteSpace($explicitShow)) {
                $info.ShowName = $explicitShow
            }
            $info.IsReliable = $true
            $info.ParseMode  = 'ordinal-season'
            return (Confirm-TVInfoShowNameAllowed -Info $info -DisallowedShowNameKeys $disallowedShowNameKeys -OriginalName $name)
        }
        # Season resolved but episode unknown — record season so the error
        # message can give a targeted hint.
        $info.Season     = $ordinalSeason
        $explicitShow = Get-TVShowNameBeforeOrdinalSeasonToken $baseName
        if (-not [string]::IsNullOrWhiteSpace($explicitShow)) {
            $info.ShowName = $explicitShow
        }
        $info.ParseError = "Ordinal season ($ordinalSeason) found in '$name' but no episode number could be extracted. Add an Episode N, Ep N, E01, or bare trailing number (e.g. '- 03') to the filename."
        return $info
    }

    # Filename-position special markers are authoritative only when paired
    # with a credible episode token. Explicit/folder seasons have already won.
    if ($baseName -match '(?i)(?:^|[\s._-])(?:OVA|OAV|ONA|Special)(?:s)?(?:$|[\s._-])') {
        $episode = Get-TVEpisodeFromFilename $name
        if ($null -eq $episode) { $episode = Get-TVEpisodeFromStrippedName $baseName }
        if ($null -ne $episode -and [int]$episode -ge 1 -and [int]$episode -le 999) {
            $info.Season = 0
            $info.Episode = [int]$episode
            $explicitShow = Get-TVShowNameBeforeSpecialMarker $baseName
            if ([string]::IsNullOrWhiteSpace($explicitShow)) {
                $explicitShow = Get-TVShowNameBeforeExplicitEpisodeToken $baseName
            }
            if (-not [string]::IsNullOrWhiteSpace($explicitShow)) { $info.ShowName = $explicitShow }
            $info.IsReliable = $true
            $info.ParseMode = 'filename-special'
            return (Confirm-TVInfoShowNameAllowed -Info $info -DisallowedShowNameKeys $disallowedShowNameKeys -OriginalName $name)
        }
    }

    if ($script:AggressiveEpisodeParsing) {
        $looseSeasonEpisode = Get-TVLooseSeasonEpisodeFromName $baseName
        if ($looseSeasonEpisode) {
            $info.Season     = [int]$looseSeasonEpisode.Season
            $info.Episode    = [int]$looseSeasonEpisode.Episode
            $info.ShowName   = $fallbackShow
            $info.IsReliable = $true
            $info.ParseMode  = "aggressive-$($looseSeasonEpisode.Mode)"
            return (Confirm-TVInfoShowNameAllowed -Info $info -DisallowedShowNameKeys $disallowedShowNameKeys -OriginalName $name)
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
            if ([string]::IsNullOrWhiteSpace($explicitShow)) {
                $explicitShow = Get-TVShowNameBeforeBareEpisodeToken -BaseName $baseName -Episode ([int]$looseEpisode.Episode)
            }
            if (-not [string]::IsNullOrWhiteSpace($explicitShow)) {
                $info.ShowName = $explicitShow
            } else {
                $info.ShowName = $fallbackShow
            }
            $info.IsReliable = $true
            $info.ParseMode  = 'default-season+episode'
            return (Confirm-TVInfoShowNameAllowed -Info $info -DisallowedShowNameKeys $disallowedShowNameKeys -OriginalName $name)
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
    $canonicalMarker = [regex]::Match($name, '(?i)(?<![A-Za-z0-9])S\d{1,2}E\d{1,3}(?:(?:E|[-_]E)\d{1,3})?(?:v\d+)?(?![A-Za-z0-9])')
    if ($canonicalMarker.Success) {
        $afterMarker = $name.Substring($canonicalMarker.Index + $canonicalMarker.Length)
        if ($afterMarker -match '^\s*[-]\s*(.+?)(?:\s*[\[\(]|\s*\.\w+$)') { return $Matches[1].Trim() }
        return ""
    }
    if ($name -match '\d{1,2}x\d{1,2}\s*[-]\s*(.+?)(?:\s*[\[\(]|\s*\.\w+$)')         { return $Matches[1].Trim() }
    if ($name -match '(?i)(?<![A-Za-z0-9])E\d{1,3}(?:v\d+)?\s*[-]\s*(.+?)(?:\s*[\[\(]|\s*\.\w+$)') { return $Matches[1].Trim() }
    if ($name -match '(?i)Episode\s*\d{1,3}\s*[-]\s*(.+?)(?:\s*[\[\(]|\s*\.\w+$)')   { return $Matches[1].Trim() }
    if ($name -match '(?i)Ep\s*\d{1,3}\s*[-]\s*(.+?)(?:\s*[\[\(]|\s*\.\w+$)')         { return $Matches[1].Trim() }
    $explicitTitle = [regex]::Match($name, '(?i)(?<![A-Za-z0-9])(?:Episode|Ep|E)[\s._-]*\d{1,3}(?![A-Za-z0-9])[\s._-]+(?<title>.+)$')
    if ($explicitTitle.Success) {
        $candidate = $explicitTitle.Groups['title'].Value
        $sourceTag = [regex]::Match($candidate, '(?i)\b(?:2160p|1080p|720p|480p|uhd|hdr10\+?|hdr|dv|dolby[\s._-]*vision|hevc|h\.?264|h\.?265|x264|x265|av1|10[\s._-]*bits?|8[\s._-]*bits?|upscale(?:d)?|bd|bdrip|blu[\s._-]*ray|bluray|web[\s._-]*dl|webdl|webrip|web|hdtv|dvd|dvdrip|remux|proper|repack|rerip|dual[\s._-]*audio|multi[\s._-]*audio|eng[\s._-]*subs?|multi[\s._-]*subs?|subs?|subbed|dubbed|flac|aac|opus|ac3|eac3|ddp\d*|ddp|dts|truehd|atmos|mkv|mp4)\b')
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

function Get-NamingRenameTVFilterCategoryNames {
    return @(
        'video_source',
        'audio_channels',
        'release_flags',
        'services_containers',
        'languages_subs_dubs',
        'release_groups'
    )
}

function Get-NamingRenameTVFilterDefaultOptions {
    $options = [ordered]@{}
    foreach ($category in @(Get-NamingRenameTVFilterCategoryNames)) {
        $options[$category] = $true
    }
    return $options
}

function Get-NamingRenameTVFilterDefaultTerms {
    return [ordered]@{
        video_source = @(
            '2160p','1080p','720p','480p','uhd','hdr','hdr10','dv','dolby vision',
            'hevc','h264','h.264','h265','h.265','x264','x265','av1','bd','bdrip',
            'blu ray','blu-ray','bluray','web dl','webdl','webrip','hdtv','dvd','dvdrip',
            'remux','10 bit','8 bit'
        )
        audio_channels = @(
            'flac','aac','opus','ac3','eac3','ddp','dts','truehd','atmos',
            '1.0','2.0','5.1','7.1','6ch','6 ch','8ch','8 ch'
        )
        release_flags = @('proper','repack','rerip','uncensored','censored')
        services_containers = @('mkv','mp4')
        languages_subs_dubs = @(
            'dual audio','multi audio','eng sub','eng subs','multi sub','multi subs',
            'subs','sub','subbed','dubbed'
        )
        release_groups = @(
            'chotab','subsplease','erai raws','erai-raws','judas','ember','bonkai','neohevc',
            'animetime','lostyears','nai','asw','sam','tnp','dedsec','mtbb','smugcat','commie',
            'horriblesubs','kametsu','db','kawaiika','tlacatlc6','ttga'
        )
    }
}

function Get-NamingRenameTVFilterOptions {
    $options = Get-NamingRenameTVFilterDefaultOptions
    $rawOptions = Get-NamingScriptConfigValue -Name 'RenameTVFilterOptions'
    foreach ($category in @(Get-NamingRenameTVFilterCategoryNames)) {
        $value = Get-NamingMapValue -Map $rawOptions -Key $category
        if ($null -ne $value) {
            $options[$category] = ConvertTo-NamingConfigBool -Value $value -Default $true
        }
    }
    return $options
}

function Test-NamingRenameTVFilterCategoryEnabled {
    param($Options, [string]$Category)

    if ($null -eq $Options) { return $true }
    $value = Get-NamingMapValue -Map $Options -Key $Category
    return ConvertTo-NamingConfigBool -Value $value -Default $true
}

function Get-NamingRenameTVFilterTermsForCategory {
    param([string]$Category)

    $defaults = Get-NamingRenameTVFilterDefaultTerms
    $rawTerms = Get-NamingScriptConfigValue -Name 'RenameTVFilterTerms'
    $configuredTerms = ConvertTo-NamingRenameMovieTermList -Value (Get-NamingMapValue -Map $rawTerms -Key $Category)
    $seen = @{}
    $terms = [System.Collections.Generic.List[string]]::new()
    foreach ($term in @($defaults[$Category]) + @($configuredTerms)) {
        $text = ([string]$term).Trim()
        if ([string]::IsNullOrWhiteSpace($text)) { continue }
        $key = $text.ToLowerInvariant()
        if ($seen.ContainsKey($key)) { continue }
        $seen[$key] = $true
        [void]$terms.Add($text)
    }
    return @($terms)
}

function Get-NamingRenameTVConfiguredTermsForCategory {
    param([string]$Category)

    # Preserve lexical uses of the few built-in words that are also common
    # title text. All other defaults and operator-supplied additions remain
    # active while PreserveTitleTerms is in effect.
    $ambiguousTitleTerms = @('web', 'proper')
    return @(Get-NamingRenameTVFilterTermsForCategory -Category $Category | Where-Object {
        ([string]$_).Trim().ToLowerInvariant() -notin $ambiguousTitleTerms
    })
}

function Get-NamingRenameTVRemoveTerms {
    $variable = Get-Variable -Name 'RenameTVRemoveTerms' -Scope Script -ErrorAction SilentlyContinue
    if ($null -eq $variable) {
        return @('sample','trailer','extras','featurette','deleted scenes','behind the scenes')
    }
    return @(ConvertTo-NamingRenameMovieTermList -Value $variable.Value)
}

function Remove-NamingTVReleaseGroups {
    param([string]$Text, $Options)

    if (-not (Test-NamingRenameTVFilterCategoryEnabled -Options $Options -Category 'release_groups')) {
        return [string]$Text
    }
    $result = [string]$Text
    foreach ($group in @(Get-NamingRenameTVFilterTermsForCategory -Category 'release_groups')) {
        $pattern = ConvertTo-NamingMovieFilterTermPattern -Term ([string]$group) -Bounded $false
        if ([string]::IsNullOrWhiteSpace($pattern)) { continue }
        $result = $result -replace "(?i)^\s*[\[\(]?\s*$pattern\s*[\]\)]?[\s._-]+", ' '
        $result = $result -replace "(?i)[\s._-]+[\[\(]?\s*$pattern\s*[\]\)]?\s*$", ' '
    }
    return $result
}

function Get-CleanTVOutputNamePart {
    param(
        [string]$Text,
        [switch]$PreserveTitleTerms
    )

    if ([string]::IsNullOrWhiteSpace($Text)) { return "" }

    $clean = Remove-PriorityMarkersFromName ([System.IO.Path]::GetFileNameWithoutExtension($Text))
    $filterOptions = Get-NamingRenameTVFilterOptions
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
    $clean = $clean -replace '(?i)\b(?:season|s)\s*\d{1,2}\s*(?:\+\s*(?:sp|specials?))?\b', ' '
    $clean = $clean -replace '(?i)\b(?:specials?|ova|oav|ona|cour)\b', ' '
    if ($PreserveTitleTerms) {
        # Category policy remains active, except for built-in words that are
        # ambiguous with legitimate show or episode-title text.
        foreach ($category in @('video_source','audio_channels','release_flags','services_containers','languages_subs_dubs','release_groups')) {
            if (Test-NamingRenameTVFilterCategoryEnabled -Options $filterOptions -Category $category) {
                $clean = Remove-NamingMovieFilterTerms -Text $clean -Terms (Get-NamingRenameTVConfiguredTermsForCategory -Category $category)
            }
        }
    } else {
        foreach ($category in @('video_source','audio_channels','release_flags','services_containers','languages_subs_dubs')) {
            if (Test-NamingRenameTVFilterCategoryEnabled -Options $filterOptions -Category $category) {
                $clean = Remove-NamingMovieFilterTerms -Text $clean -Terms (Get-NamingRenameTVFilterTermsForCategory -Category $category)
            }
        }
        $clean = Remove-NamingTVReleaseGroups -Text $clean -Options $filterOptions
    }
    $clean = Remove-NamingMovieFilterTerms -Text $clean -Terms (Get-NamingRenameTVRemoveTerms)
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

    # Revision flags are metadata only when they occupy the release-tail
    # position. Lexical uses such as "A Proper Introduction" remain titles.
    $titleText = [string]$Title -replace '(?i)[\s._-]+(?:PROPER|REPACK|RERIP)\s*$', ' '
    $clean = Get-CleanTVOutputNamePart -Text $titleText -PreserveTitleTerms
    if ([string]::IsNullOrWhiteSpace($clean)) { return "" }
    if ($clean.Length -gt 80) { return "" }
    if ($clean -match '^\d+$') { return "" }
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

function Get-CleanTVFilename {
    param($tvInfo, [string]$origName)
    return (New-PlexTVDestinationPlan -TvInfo $tvInfo -OriginalName $origName).FileBaseName
}

function Get-TVParseRenameSuggestion {
    param($File, $TvInfo)

    $ext = [System.IO.Path]::GetExtension($File.Name)
    if ($TvInfo -and $null -ne $TvInfo.Season -and [int]$TvInfo.Season -ge 0 -and $TvInfo.ShowName) {
        $show = Get-CleanTVOutputNamePart -Text ([string](Get-TVInfoField -TvInfo $TvInfo -Name 'ShowName' -Default '')) -PreserveTitleTerms
        if ([string]::IsNullOrWhiteSpace($show)) { $show = ([string]$TvInfo.ShowName -replace '[<>:"/\\|?*]', '').Trim() }
        return ("{0} - S{1}E##{2}" -f $show, ([int]$TvInfo.Season).ToString('00'), $ext)
    }
    return "Show Name - S01E01$ext"
}
