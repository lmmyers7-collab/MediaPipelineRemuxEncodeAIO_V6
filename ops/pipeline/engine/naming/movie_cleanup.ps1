# ==============================================================================
# ops\pipeline\engine\naming\movie_cleanup.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\naming\naming.ps1. Keep function names stable;
# naming.ps1 dot-sources this file as the public compatibility surface.
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

function Get-NamingRenameMovieFilterCategoryNames {
    return @(
        'video_source',
        'audio_channels',
        'editions',
        'file_size',
        'services_containers',
        'release_groups'
    )
}

function Get-NamingRenameMovieFilterDefaultOptions {
    $options = [ordered]@{}
    foreach ($category in @(Get-NamingRenameMovieFilterCategoryNames)) {
        $options[$category] = $true
    }
    return $options
}

function Get-NamingRenameMovieFilterDefaultTerms {
    return [ordered]@{
        video_source = @(
            '2160p','1080p','1080i','720p','720i','480p','4k','uhd','hdr','hdr10','hdr10+','hlg','dv','dovi',
            'dolby vision','hevc','h264','h.264','h265','h.265','x264','x265','av1','avc','xvid','divx',
            'blu ray','bluray','brrip','bdrip','webrip','web dl','webdl','web','hdtv','hdrip','dvdrip','dvd',
            'dvdscr','ts','cam','scr','remux','hybrid','10 bit','8 bit'
        )
        audio_channels = @(
            'truehd','atmos','flac','opus','eac3','ac3','aac','dd','dd+','ddp','dts','dts hd','dts-x','dtsx',
            'dtshd','lpcm','pcm','mp3','mp2','1.0','2.0','5.1','7.1','stereo','mono','6ch','6 ch','8ch','8 ch'
        )
        editions = @(
            'imax','proper','repack','rerip','extended','remastered','remaster','restored','restoration','unrated',
            'theatrical','criterion','director cut','directors cut',"director's cut",'dc','final cut','open matte',
            'redux','special edition','se','anniversary','collectors edition','supercut'
        )
        file_size = @(
            '500mb','700mb','1400mb','1gb','1.5gb','2gb','3gb','4.7gb','5gb','6gb','8gb','10gb','15gb','20gb','25gb','30gb'
        )
        services_containers = @(
            'amzn','nf','dsnp','hmax','hulu','itunes','appletv','atvp','peacock','pck','vudu','stan','sho','mkv','mp4','m4v','avi','mov','wmv'
        )
        release_groups = @(
            'rarbg','rbg','yify','yts','yts lt','galaxyrg','bone','psa','tigole','kris','sparks','ntb','evo','tepes','flux','framestor','cmrg','neonoir'
        )
    }
}

function Get-NamingRenameMovieRemoveTermsDefault {
    return @('sample','trailer','extras','featurette','deleted scenes','behind the scenes')
}

function Get-NamingScriptConfigValue {
    param([string]$Name)

    $variable = Get-Variable -Name $Name -Scope Script -ErrorAction SilentlyContinue
    if ($null -ne $variable) { return $variable.Value }
    return $null
}

function ConvertTo-NamingConfigBool {
    param($Value, [bool]$Default = $true)

    if ($Value -is [bool]) { return [bool]$Value }
    if ($null -eq $Value) { return $Default }
    if ($Value -is [int] -or $Value -is [long] -or $Value -is [double]) { return [bool]$Value }
    $text = ([string]$Value).Trim().ToLowerInvariant()
    if ($text -in @('true','1','yes','y','on')) { return $true }
    if ($text -in @('false','0','no','n','off')) { return $false }
    return $Default
}

function Get-NamingMapValue {
    param($Map, [string]$Key)

    if ($null -eq $Map) { return $null }
    if ($Map -is [System.Collections.IDictionary]) {
        if ($Map.Contains($Key)) { return $Map[$Key] }
        return $null
    }
    $property = $Map.PSObject.Properties[$Key]
    if ($null -ne $property) { return $property.Value }
    return $null
}

function ConvertTo-NamingRenameMovieTermList {
    param($Value)

    if ($null -eq $Value) { return @() }
    $rawValues = @()
    if ($Value -is [string]) {
        $rawValues = @($Value -split '[,;\r\n]+')
    } elseif ($Value -is [System.Collections.IEnumerable]) {
        $rawValues = @($Value)
    } else {
        $rawValues = @($Value)
    }
    $seen = @{}
    $terms = New-Object System.Collections.Generic.List[string]
    foreach ($raw in $rawValues) {
        $term = ([string]$raw).Trim()
        if ([string]::IsNullOrWhiteSpace($term)) { continue }
        $key = $term.ToLowerInvariant()
        if ($seen.ContainsKey($key)) { continue }
        $seen[$key] = $true
        [void]$terms.Add($term)
    }
    return @($terms)
}

function Get-NamingRenameMovieFilterOptions {
    $options = Get-NamingRenameMovieFilterDefaultOptions
    $rawOptions = Get-NamingScriptConfigValue -Name 'RenameMovieFilterOptions'
    foreach ($category in @(Get-NamingRenameMovieFilterCategoryNames)) {
        $value = Get-NamingMapValue -Map $rawOptions -Key $category
        if ($null -ne $value) {
            $options[$category] = ConvertTo-NamingConfigBool -Value $value -Default $true
        }
    }
    return $options
}

function Test-NamingRenameMovieFilterCategoryEnabled {
    param($Options, [string]$Category)

    if ($null -eq $Options) { return $true }
    $value = Get-NamingMapValue -Map $Options -Key $Category
    return ConvertTo-NamingConfigBool -Value $value -Default $true
}

function Get-NamingRenameMovieFilterTermsForCategory {
    param([string]$Category)

    $defaults = Get-NamingRenameMovieFilterDefaultTerms
    $rawTerms = Get-NamingScriptConfigValue -Name 'RenameMovieFilterTerms'
    $configuredTerms = ConvertTo-NamingRenameMovieTermList -Value (Get-NamingMapValue -Map $rawTerms -Key $Category)
    $seen = @{}
    $terms = New-Object System.Collections.Generic.List[string]
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

function Get-NamingRenameMovieRemoveTerms {
    $configured = Get-NamingScriptConfigValue -Name 'RenameMovieRemoveTerms'
    $terms = ConvertTo-NamingRenameMovieTermList -Value $configured
    if ($terms.Count -gt 0) { return @($terms) }
    return @(Get-NamingRenameMovieRemoveTermsDefault)
}

function ConvertTo-NamingMovieFilterTermPattern {
    param([string]$Term, [bool]$Bounded = $true)

    $pieces = @([regex]::Split(([string]$Term).Trim(), '[\s._-]+') | Where-Object {
        -not [string]::IsNullOrWhiteSpace([string]$_)
    } | ForEach-Object {
        [regex]::Escape([string]$_)
    })
    if ($pieces.Count -eq 0) { return '' }
    $body = ($pieces -join '[\s._-]*')
    if (-not $Bounded) { return $body }
    return "(?<![A-Za-z0-9])$body(?![A-Za-z0-9])"
}

function Remove-NamingMovieFilterTerms {
    param([string]$Text, [array]$Terms)

    $result = [string]$Text
    foreach ($term in @($Terms)) {
        $pattern = ConvertTo-NamingMovieFilterTermPattern -Term ([string]$term)
        if ([string]::IsNullOrWhiteSpace($pattern)) { continue }
        $result = [regex]::Replace($result, $pattern, ' ', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    }
    return $result
}

function Get-CleanMovieName {
    param([string]$FileName)

    $base = Remove-PriorityMarkersFromName ([System.IO.Path]::GetFileNameWithoutExtension($FileName))
    $filterOptions = Get-NamingRenameMovieFilterOptions

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
    if (Test-NamingRenameMovieFilterCategoryEnabled -Options $filterOptions -Category 'file_size') {
        $title = $title -replace '\b\d+(?:\.\d+)?\s*(?:mb|gb)\b', ' '
        $title = Remove-NamingMovieFilterTerms -Text $title -Terms (Get-NamingRenameMovieFilterTermsForCategory -Category 'file_size')
    }
    if (Test-NamingRenameMovieFilterCategoryEnabled -Options $filterOptions -Category 'audio_channels') {
        $title = $title -replace '\b(?:truehd|atmos|flac|opus|eac3|ac3|aac|ddp?|dts(?:[\s._-]*hd)?|dtshd)(?:[\s._-]*(?:1\.0|2\.0|5\.1|7\.1|6ch|8ch))?\b|\b(?:1\.0|2\.0|5\.1|7\.1|6\s*ch|8\s*ch)\b', ' '
        $title = Remove-NamingMovieFilterTerms -Text $title -Terms (Get-NamingRenameMovieFilterTermsForCategory -Category 'audio_channels')
    }
    if (Test-NamingRenameMovieFilterCategoryEnabled -Options $filterOptions -Category 'video_source') {
        $title = $title -replace '\b(?:2160p|1080p|720p|480p|uhd|hdr|hdr10\+?|dv|dovi|dolby[\s._-]*vision|hevc|h\.?264|h\.?265|x264|x265|av1|avc|blu[\s._-]*ray|brrip|bdrip|webrip|web[\s._-]*dl|webdl|web|hdtv|dvdrip|dvd|remux)\b', ' '
        $title = $title -replace '\b(?:10|8)\s*bit\b', ' '
        $title = Remove-NamingMovieFilterTerms -Text $title -Terms (Get-NamingRenameMovieFilterTermsForCategory -Category 'video_source')
    }
    if (Test-NamingRenameMovieFilterCategoryEnabled -Options $filterOptions -Category 'editions') {
        $title = $title -replace '\b(?:imax|proper|repack|rerip|extended|remastered|remaster|unrated|theatrical|criterion|directors?[\s._-]*cut|final[\s._-]*cut|open[\s._-]*matte)\b', ' '
        $title = Remove-NamingMovieFilterTerms -Text $title -Terms (Get-NamingRenameMovieFilterTermsForCategory -Category 'editions')
    }
    if (Test-NamingRenameMovieFilterCategoryEnabled -Options $filterOptions -Category 'services_containers') {
        $title = $title -replace '\b(?:amzn|nf|dsnp|hmax|hulu|itunes|appletv|mkv|mp4|m4v)\b', ' '
        $title = Remove-NamingMovieFilterTerms -Text $title -Terms (Get-NamingRenameMovieFilterTermsForCategory -Category 'services_containers')
    }
    $title = Remove-NamingMovieFilterTerms -Text $title -Terms (Get-NamingRenameMovieRemoveTerms)

    if (Test-NamingRenameMovieFilterCategoryEnabled -Options $filterOptions -Category 'release_groups') {
        foreach ($group in @(Get-NamingRenameMovieFilterTermsForCategory -Category 'release_groups')) {
            $groupPattern = ConvertTo-NamingMovieFilterTermPattern -Term ([string]$group) -Bounded $false
            if ([string]::IsNullOrWhiteSpace($groupPattern)) { continue }
            $title = $title -replace "(?i)^\s*[\[\(]?\s*$groupPattern\s*[\]\)]?[\s._-]+", ' '
            $title = $title -replace "(?i)[\s._-]+[\[\(]?\s*$groupPattern\s*[\]\)]?\s*$", ' '
        }
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

