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
    $preservedUppercaseTokens = @('dc')
    $tokens = New-Object System.Collections.Generic.List[string]
    $rawTokens = @($Value -split '\s+' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $previousLower = ''

    for ($i = 0; $i -lt $rawTokens.Count; $i++) {
        $word = [string]$rawTokens[$i]
        if ($word -ceq $word.ToUpperInvariant()) {
            $word = $word.ToLowerInvariant()
        }
        $lower = $word.ToLowerInvariant()
        if ($preservedUppercaseTokens.Contains($lower)) {
            $formatted = $lower.ToUpperInvariant()
        } elseif ($romanNumerals.Contains($lower)) {
            $formatted = $lower.ToUpperInvariant()
        } elseif ($lower -eq 'the') {
            if (($i -gt 0) -and $lowerTheAfter.Contains($previousLower)) {
                $formatted = 'the'
            } else {
                $formatted = 'The'
            }
        } elseif (($i -gt 0) -and $smallWords.Contains($lower)) {
            $previousRaw = [string]$rawTokens[$i - 1]
            $formatted = if ($lower -eq 'a' -and $previousRaw -match '^\d+$') { 'A' } else { $lower }
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

function Get-NamingMovieRightmostYearInfo {
    param([string]$Text)

    $maximumPlausibleYear = (Get-Date).Year + 1
    $plausibleMatches = @([regex]::Matches([string]$Text, '(?<!\d)(?:18|19|20)\d{2}(?!\d)') | Where-Object {
        $candidate = [int]$_.Value
        $candidate -ge 1888 -and $candidate -le $maximumPlausibleYear
    })
    if ($plausibleMatches.Count -eq 0) { return $null }

    $annotated = @($plausibleMatches | ForEach-Object {
        $candidate = $_
        $prefix = ([string]$Text).Substring(0, $candidate.Index)
        $suffix = ([string]$Text).Substring($candidate.Index + $candidate.Length)
        [pscustomobject]@{
            Match       = $candidate
            IsBracketed = [bool]($prefix -match '[\(\[\{]\s*$' -and $suffix -match '^\s*[\)\]\}]')
        }
    })
    $bracketed = @($annotated | Where-Object { $_.IsBracketed })
    $selected = if ($bracketed.Count -gt 0) { $bracketed[$bracketed.Count - 1] } else { $annotated[$annotated.Count - 1] }
    $match = $selected.Match

    # A lone plausible number is a numeric title, not evidence of a release
    # year. A second title token (including an earlier number) is required.
    if (-not $selected.IsBracketed) {
        $withoutCandidate = ([string]$Text).Remove($match.Index, $match.Length)
        $meaningfulRemainder = $withoutCandidate -replace '[\s._\-\(\)\[\]\{\}]+', ''
        if ([string]::IsNullOrWhiteSpace($meaningfulRemainder)) { return $null }
    }

    return [pscustomobject]@{
        Value       = [string]$match.Value
        Index       = [int]$match.Index
        Length      = [int]$match.Length
        IsBracketed = [bool]$selected.IsBracketed
    }
}

function Protect-NamingMovieAmbiguousTitleTerms {
    param(
        [string]$Text,
        $YearInfo = $null
    )

    $protectedEnd = ([string]$Text).Length
    if ($YearInfo -and -not [bool]$YearInfo.IsBracketed) {
        $yearMatches = [regex]::Matches([string]$Text, "(?<!\d)$([regex]::Escape([string]$YearInfo.Value))(?!\d)")
        if ($yearMatches.Count -gt 0) {
            $protectedEnd = [int]$yearMatches[$yearMatches.Count - 1].Index
        }
    }

    # A strong, non-ambiguous technical marker starts a verified release tail.
    # Bare words such as Web, Cam, DC, Ma, Audio, and Proper are deliberately
    # excluded because they can be legitimate title text.
    $strongTail = [regex]::Match([string]$Text, '(?i)(?<![A-Za-z0-9])(?:2160p|1080[pi]|720[pi]|480p|4k|uhd|hdr10\+?|hdr|dovi|dolby[\s._-]*vision|hevc|h\.?264|h\.?265|x264|x265|av1|avc|xvid|divx|blu[\s._-]*ray|bluray|brrip|bdrip|webrip|web[\s._-]*dl|webdl|hdtv|dvdrip|dvd|remux|truehd|atmos|flac|opus|eac3|ac3|aac|ddp?|dts(?:[\s._-]*hd)?|dtshd|\d+(?:\.\d+)?[\s._-]*(?:mb|gb))(?![A-Za-z0-9])')
    if ($strongTail.Success -and $strongTail.Index -lt $protectedEnd) {
        $protectedEnd = [int]$strongTail.Index
    }

    # Revision flags immediately before the release year are verified tail
    # metadata. Keep them outside the protected title region while preserving
    # uses such as "A Proper Man".
    if ($protectedEnd -gt 0) {
        $prefix = ([string]$Text).Substring(0, $protectedEnd)
        $revisionTail = [regex]::Match($prefix, '(?i)(?:[\s._-]+(?:proper|repack|rerip))+[\s._-]*$')
        if ($revisionTail.Success) {
            $protectedEnd = [int]$revisionTail.Index
        }
    }

    $matches = @([regex]::Matches([string]$Text, '(?i)(?<![A-Za-z0-9])(?:web|cam|dc|ma|audio|proper)(?![A-Za-z0-9])') | Where-Object {
        ($_.Index + $_.Length) -le $protectedEnd
    })
    if ($matches.Count -eq 0) {
        return [pscustomobject]@{ Text = [string]$Text; Replacements = @() }
    }

    $result = [string]$Text
    $replacements = New-Object System.Collections.Generic.List[object]
    for ($i = $matches.Count - 1; $i -ge 0; $i--) {
        $match = $matches[$i]
        $placeholder = "MPAMBIGUOUSTITLE$($i)TOKEN"
        $result = $result.Remove($match.Index, $match.Length).Insert($match.Index, $placeholder)
        [void]$replacements.Add([pscustomobject]@{
            Placeholder = $placeholder
            Value       = [string]$match.Value
        })
    }
    return [pscustomobject]@{ Text = $result; Replacements = $replacements.ToArray() }
}

function Restore-NamingMovieAmbiguousTitleTerms {
    param([string]$Text, [array]$Replacements)

    $result = [string]$Text
    foreach ($replacement in @($Replacements)) {
        $result = [regex]::Replace(
            $result,
            [regex]::Escape([string]$replacement.Placeholder),
            [System.Text.RegularExpressions.MatchEvaluator]{ param($match) [string]$replacement.Value },
            [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
        )
    }
    return $result
}

function Get-NamingRenameMovieFilterCategoryNames {
    return @(
        'video_source',
        'audio_channels',
        'editions',
        'file_size',
        'services_containers',
        'languages_subs_dubs',
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
            'dvdscr','ts','cam','scr','remux','hybrid','10 bit','10bit','10 bits','10bits','10-bit','10-bits',
            '8 bit','8bit','8 bits','8bits','8-bit','8-bits','upscale','upscaled'
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
        languages_subs_dubs = @(
            'eng','ita','fre','fra','ger','deu','spa','esp','jpn','jap','kor','chi','zho','rus','por','dut','nld','swe','dan','nor',
            'fin','pol','cze','ces','hun','gre','ell','tur','ara','hin','tha','vie','ukr','sub','subs','subbed','dub','dubs',
            'dubbed','multi audio','dual audio','dual-audio','multi','audio','vostfr','vose'
        )
        release_groups = @(
            'rarbg','rbg','yify','yts','yts lt','galaxyrg','bone','psa','tigole','kris','sparks','ntb','evo','tepes','flux','framestor','cmrg','neonoir',
            'asiimov','rapta','licdom'
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
    if ($terms.Count -gt 0) {
        $defaults = @(Get-NamingRenameMovieRemoveTermsDefault)
        $legacyPackagedTerms = @($defaults) + @(1..12 | ForEach-Object { $_.ToString('00') })
        if ($terms.Count -eq $legacyPackagedTerms.Count) {
            $configuredKeys = @($terms | ForEach-Object { ([string]$_).ToLowerInvariant() })
            $isExactLegacyList = -not @($legacyPackagedTerms | Where-Object {
                ([string]$_).ToLowerInvariant() -notin $configuredKeys
            }).Count
            if ($isExactLegacyList) {
                return $defaults
            }
        }
        return @($terms)
    }
    return @(Get-NamingRenameMovieRemoveTermsDefault)
}

function ConvertTo-NamingMovieFilterTermPattern {
    param([string]$Term, [bool]$Bounded = $true)

    $trimmedTerm = ([string]$Term).Trim()
    if ($trimmedTerm -match '^\d\.\d$') {
        $decimalPattern = [regex]::Escape($trimmedTerm)
        if (-not $Bounded) { return $decimalPattern }
        return "(?<![A-Za-z0-9])$decimalPattern(?![A-Za-z0-9])"
    }

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

    # Prefer a bracketed plausible release year; otherwise use the rightmost
    # plausible year. Earlier values can be legitimate title text (2001,
    # Blade Runner 2049, 1917, or 1984). Cinema predates 1888, future values
    # beyond next year are title text, and a lone number is a numeric title.
    $yearInfo = Get-NamingMovieRightmostYearInfo -Text $base
    $year = if ($yearInfo) { [string]$yearInfo.Value } else { '' }

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
    $ambiguousTitleProtection = Protect-NamingMovieAmbiguousTitleTerms -Text $title -YearInfo $yearInfo
    $title = [string]$ambiguousTitleProtection.Text
    if (Test-NamingRenameMovieFilterCategoryEnabled -Options $filterOptions -Category 'file_size') {
        $title = $title -replace '\b\d+(?:\.\d+)?\s*(?:mb|gb)\b', ' '
        $title = Remove-NamingMovieFilterTerms -Text $title -Terms (Get-NamingRenameMovieFilterTermsForCategory -Category 'file_size')
    }
    if (Test-NamingRenameMovieFilterCategoryEnabled -Options $filterOptions -Category 'audio_channels') {
        $title = $title -replace '\b(?:truehd|atmos|flac|opus|eac3|ac3|aac|ddp?|dts(?:[\s._-]*hd)?|dtshd)(?:[\s._-]*(?:1\.0|2\.0|5\.1|7\.1|6ch|8ch))?\b|\b(?:1\.0|2\.0|5\.1|7\.1|6\s*ch|8\s*ch)\b', ' '
        $title = Remove-NamingMovieFilterTerms -Text $title -Terms (Get-NamingRenameMovieFilterTermsForCategory -Category 'audio_channels')
    }
    if (Test-NamingRenameMovieFilterCategoryEnabled -Options $filterOptions -Category 'video_source') {
        $title = $title -replace '(?i)(?<![A-Za-z0-9])hdr10\+?(?![A-Za-z0-9])', ' '
        $title = $title -replace '\b(?:2160p|1080p|720p|480p|uhd|hdr|hdr10\+?|dv|dovi|dolby[\s._-]*vision|hevc|h\.?264|h\.?265|x264|x265|av1|avc|blu[\s._-]*ray|brrip|bdrip|webrip|web[\s._-]*dl|webdl|web|hdtv|dvdrip|dvd|remux|upscale(?:d)?)\b', ' '
        $title = $title -replace '\b(?:10|8)[\s._-]*bits?\b', ' '
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
    if (Test-NamingRenameMovieFilterCategoryEnabled -Options $filterOptions -Category 'languages_subs_dubs') {
        $title = Remove-NamingMovieFilterTerms -Text $title -Terms (Get-NamingRenameMovieFilterTermsForCategory -Category 'languages_subs_dubs')
    }
    $title = Remove-NamingMovieFilterTerms -Text $title -Terms (Get-NamingRenameMovieRemoveTerms)

    if (Test-NamingRenameMovieFilterCategoryEnabled -Options $filterOptions -Category 'release_groups') {
        foreach ($group in @(Get-NamingRenameMovieFilterTermsForCategory -Category 'release_groups')) {
            $groupPattern = ConvertTo-NamingMovieFilterTermPattern -Term ([string]$group) -Bounded $false
            if ([string]::IsNullOrWhiteSpace($groupPattern)) { continue }
            $title = $title -replace "(?i)^\s*[\[\(]?\s*$groupPattern\s*[\]\)]?[\s._-]+", ' '
            $title = $title -replace "(?i)[\s._-]+[\[\(]?\s*$groupPattern\s*[\]\)]?\s*$", ' '
            if ($yearInfo -and -not [bool]$yearInfo.IsBracketed) {
                $escapedYear = [regex]::Escape([string]$yearInfo.Value)
                $title = $title -replace "(?i)[\s._-]+[\[\(]?\s*$groupPattern\s*[\]\)]?(?=[\s._-]+$escapedYear(?:[\s._-]*$))", ' '
            }
        }
    }

    $title = Restore-NamingMovieAmbiguousTitleTerms -Text $title -Replacements @($ambiguousTitleProtection.Replacements)

    # Convert separators (dots, underscores, hyphens-between-words) to spaces.
    # We handle hyphens carefully: "Spider-Man" should keep the hyphen,
    # but "Title - Subtitle - 2024" should lose them. Our rule: a hyphen
    # surrounded by spaces acts as a separator, a hyphen inside a word
    # (flanked by letters on both sides) is preserved.
    $title = $title -replace '[\._]', ' '
    $title = $title -replace '\s-\s', ' '      # " - " as separator
    $title = $title -replace '\s-|-\s',  ' '   # dangling hyphens

    # Drop exactly the selected unbracketed release-year occurrence. Removing
    # every equal token would turn "1984 1984" into an empty title.
    if ($yearInfo -and -not [bool]$yearInfo.IsBracketed) {
        $yearMatches = [regex]::Matches($title, "(?<!\d)$([regex]::Escape($year))(?!\d)")
        if ($yearMatches.Count -gt 0) {
            $yearMatch = $yearMatches[$yearMatches.Count - 1]
            $title = $title.Remove($yearMatch.Index, $yearMatch.Length).Insert($yearMatch.Index, ' ')
        }
    }

    # Collapse whitespace and strip non-filename-safe characters.
    # Preserves letters, digits, spaces, hyphens (for Spider-Man), apostrophes,
    # ampersands, commas, and exclamation marks. Filesystem-hostile chars
    # (<>:"/\|?*) are removed.
    $title = $title -replace '[<>:"/\\|?*]', ''
    $title = ($title -replace '\s+', ' ').Trim()

    $title = ConvertTo-MediaPipelineMovieTitleCase $title

    if ([string]::IsNullOrWhiteSpace($title)) {
        return ''
    }

    if ($year) { return "$title ($year)" }
    return $title
}
