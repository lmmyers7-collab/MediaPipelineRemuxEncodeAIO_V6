# Extracted from ops/pipeline/entrypoints/Audit-MediaLibrary.ps1. Responsibility: stream, subtitle, audio, and audit-row evidence

function Get-TagValue {
    param(
        $Object,
        [string]$Name
    )

    if ($null -eq $Object) { return '' }
    $prop = $Object.PSObject.Properties[$Name]
    if ($prop) { return [string]$prop.Value }
    return ''
}

function Get-StreamTagValue {
    param(
        $Stream,
        [string]$Name
    )

    if ($null -eq $Stream -or $null -eq $Stream.tags) { return '' }
    return Get-TagValue -Object $Stream.tags -Name $Name
}

function Get-StreamDispositionValue {
    param(
        $Stream,
        [string]$Name
    )

    if ($null -eq $Stream -or $null -eq $Stream.disposition) { return 0 }
    $raw = Get-TagValue -Object $Stream.disposition -Name $Name
    $value = 0
    if ([int]::TryParse([string]$raw, [ref]$value)) { return $value }
    return 0
}

function Test-AuditTx3gSubtitleStream {
    param($Stream)

    if ($null -eq $Stream) { return $false }
    $codecName = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_name')
    $codecTag = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_tag_string')
    $codecLong = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_long_name')

    return (
        $codecName -eq (Get-MediaSubtitleCodecMovTextName) -or
        $codecTag -eq 'tx3g' -or
        $codecLong -match 'timed\s*text|mpeg-4\s*timed\s*text|mp4\s*timed\s*text'
    )
}

function Test-AuditBdpgsSubtitleStream {
    param($Stream)

    if ($null -eq $Stream) { return $false }
    $codecName = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_name')
    $codecTag = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_tag_string')
    $codecLong = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_long_name')

    return (
        $codecName -in (Get-MediaSubtitleCodecBdpgsNames) -or
        $codecTag -match 'pgs' -or
        $codecLong -match 'presentation\s+graphic|blu-?ray\s+pgs|hdmv\s+pgs'
    )
}

function Test-AuditVobSubSubtitleStream {
    param($Stream)

    if ($null -eq $Stream) { return $false }
    $codecName = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_name')
    $codecTag = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_tag_string')
    $codecLong = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_long_name')

    return (
        $codecName -in (Get-MediaSubtitleCodecVobSubNames) -or
        $codecTag -match 's_vobsub|vobsub|dvd' -or
        $codecLong -match 'vobsub|dvd\s+subtitle'
    )
}

function Get-AuditTx3gGenericSrtSuffixes {
    param([array]$Tx3gSubtitleStreams)

    $suffixes = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($stream in @($Tx3gSubtitleStreams)) {
        $lang = Convert-ToLowerInvariantSafe (Get-StreamTagValue -Stream $stream -Name 'language')
        if ([string]::IsNullOrWhiteSpace($lang)) { $lang = 'und' }
        [void]$suffixes.Add($lang)
        if ((Get-StreamDispositionValue $stream 'forced') -eq 1) {
            [void]$suffixes.Add("$lang.forced")
        }
    }
    return @($suffixes | ForEach-Object { [string]$_ })
}

function Test-AuditSrtFileUsable {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or
        -not (Test-Path -LiteralPath $Path -PathType Leaf -ErrorAction SilentlyContinue)) {
        return $false
    }

    try {
        $item = Get-Item -LiteralPath $Path -ErrorAction Stop
        if ($item.Length -le 0) { return $false }
        $raw = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
        if ([string]::IsNullOrWhiteSpace($raw)) { return $false }
        $hasTiming = [regex]::IsMatch($raw, '(?m)^\s*\d{1,2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{1,2}:\d{2}:\d{2},\d{3}')
        $hasText = @(
            $raw -split '\r?\n' |
                ForEach-Object { ([string]$_).Trim() } |
                Where-Object {
                    $_ -match '\S' -and
                    $_ -notmatch '^\d+$' -and
                    $_ -notmatch '^\d{1,2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{1,2}:\d{2}:\d{2},\d{3}'
                }
        ).Count -gt 0
        return ($hasTiming -and $hasText)
    } catch {
        return $false
    }
}

function Get-AuditNormalizedPathKey {
    param(
        [string]$Path,
        [string]$BaseDirectory = ''
    )

    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    try {
        $candidate = $Path
        if (-not [System.IO.Path]::IsPathRooted($candidate) -and -not [string]::IsNullOrWhiteSpace($BaseDirectory)) {
            $candidate = Join-Path $BaseDirectory $candidate
        }
        return ([System.IO.Path]::GetFullPath($candidate)).ToLowerInvariant()
    } catch {
        return $Path.ToLowerInvariant()
    }
}

function Get-AuditSidecarSrtRecordPath {
    param(
        $Record,
        [string]$BaseDirectory = ''
    )

    $rawPath = [string](Get-TagValue -Object $Record -Name 'path')
    if ([string]::IsNullOrWhiteSpace($rawPath)) { return '' }
    if (-not [System.IO.Path]::IsPathRooted($rawPath) -and -not [string]::IsNullOrWhiteSpace($BaseDirectory)) {
        $rawPath = Join-Path $BaseDirectory $rawPath
    }
    try { return [System.IO.Path]::GetFullPath($rawPath) } catch { return $rawPath }
}

function Test-AuditTx3gSidecarSrtRecordUsable {
    param(
        $Record,
        [string]$BaseDirectory = ''
    )

    if ($null -eq $Record) { return $false }
    $status = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Record -Name 'status')
    if ($status -eq 'pending') { return $false }
    $path = Get-AuditSidecarSrtRecordPath -Record $Record -BaseDirectory $BaseDirectory
    if ([string]::IsNullOrWhiteSpace($path)) { return $false }
    return (Test-AuditSrtFileUsable -Path $path)
}

function Test-AuditEmbeddedSrtRecordMatchesStream {
    param(
        $Record,
        $Stream,
        [ValidateSet('tx3g','bdpgs','vobsub')] [string]$SourceKind = 'tx3g'
    )

    if ($null -eq $Record -or $null -eq $Stream) { return $false }
    $codec = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_name')
    if ($codec -notin (Get-MediaSubtitleCodecTextNames)) { return $false }

    $recordLang = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Record -Name 'language')
    $streamLang = Convert-ToLowerInvariantSafe (Get-StreamTagValue -Stream $Stream -Name 'language')
    if ([string]::IsNullOrWhiteSpace($recordLang)) { $recordLang = 'und' }
    if ([string]::IsNullOrWhiteSpace($streamLang)) { $streamLang = 'und' }
    if ($recordLang -notin @('', 'und') -and $streamLang -notin @('', 'und') -and $recordLang -ne $streamLang) {
        return $false
    }

    $recordTitle = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Record -Name 'title')
    $streamTitle = Convert-ToLowerInvariantSafe (Get-StreamTagValue -Stream $Stream -Name 'title')
    if (-not [string]::IsNullOrWhiteSpace($recordTitle)) {
        $recordTitle = $recordTitle.Trim()
        $streamTitle = $streamTitle.Trim()
        if ([string]::IsNullOrWhiteSpace($streamTitle)) { return $false }
        if ($streamTitle -ne $recordTitle -and -not $streamTitle.Contains($recordTitle)) { return $false }
    } elseif ($SourceKind -eq 'tx3g' -and $codec -eq (Get-MediaSubtitleCodecMovTextName)) {
        return $false
    }

    return $true
}

function Get-AuditValidatedEmbeddedSrtRecordCount {
    param(
        [array]$Records = @(),
        [array]$SubtitleStreams = @(),
        [ValidateSet('tx3g','bdpgs','vobsub')] [string]$SourceKind = 'tx3g'
    )

    $usableTextStreams = @($SubtitleStreams | Where-Object {
        (Convert-ToLowerInvariantSafe (Get-TagValue -Object $_ -Name 'codec_name')) -in (Get-MediaSubtitleCodecTextNames)
    })
    if ($usableTextStreams.Count -eq 0) { return 0 }

    $used = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    $count = 0
    foreach ($record in @($Records | Where-Object { $null -ne $_ })) {
        foreach ($stream in $usableTextStreams) {
            $streamKey = [string](Get-TagValue -Object $stream -Name 'index')
            if ([string]::IsNullOrWhiteSpace($streamKey)) { $streamKey = [guid]::NewGuid().ToString('N') }
            if ($used.Contains($streamKey)) { continue }
            if (Test-AuditEmbeddedSrtRecordMatchesStream -Record $record -Stream $stream -SourceKind $SourceKind) {
                [void]$used.Add($streamKey)
                $count++
                break
            }
        }
    }
    return $count
}

function Get-MatchingExternalSrtFilesForAudit {
    param(
        $FileInfo,
        [array]$Tx3gSubtitleStreams = @(),
        [array]$KnownTx3gSrtFiles = @()
    )

    if ($null -eq $FileInfo -or [string]::IsNullOrWhiteSpace($FileInfo.DirectoryName)) { return @() }
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($FileInfo.Name)
    if ([string]::IsNullOrWhiteSpace($baseName)) { return @() }
    $genericSuffixes = @(Get-AuditTx3gGenericSrtSuffixes -Tx3gSubtitleStreams $Tx3gSubtitleStreams)
    $knownTx3gSrtKeys = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($known in @($KnownTx3gSrtFiles)) {
        $key = Get-AuditNormalizedPathKey -Path ([string]$known) -BaseDirectory $FileInfo.DirectoryName
        if (-not [string]::IsNullOrWhiteSpace($key)) { [void]$knownTx3gSrtKeys.Add($key) }
    }

    return @(
        Get-ChildItem -LiteralPath $FileInfo.DirectoryName -Filter '*.srt' -File -ErrorAction SilentlyContinue |
            Where-Object {
                $stem = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
                if (-not $stem.StartsWith("$baseName.", [System.StringComparison]::OrdinalIgnoreCase)) {
                    $false
                } else {
                    $suffix = $stem.Substring($baseName.Length + 1).ToLowerInvariant()
                    $pathKey = Get-AuditNormalizedPathKey -Path $_.FullName
                    $isKnownTx3gSidecar = $knownTx3gSrtKeys.Contains($pathKey)
                    $isGeneratedTx3gName = ($suffix -match '(^|\.)tx3g($|\.)')
                    $isKnownGenericMatch = ($genericSuffixes -contains $suffix) -and $isKnownTx3gSidecar
                    ($isGeneratedTx3gName -or $isKnownGenericMatch) -and (Test-AuditSrtFileUsable -Path $_.FullName)
                }
            } |
            Sort-Object Name |
            ForEach-Object { $_.FullName }
    )
}

function Get-DefaultStream {
    param([array]$Streams)

    $explicit = @($Streams | Where-Object { (Get-StreamDispositionValue $_ 'default') -eq 1 } | Select-Object -First 1)
    if ($explicit.Count -gt 0) {
        return @{
            Stream      = $explicit[0]
            IsExplicit  = $true
        }
    }

    $first = @($Streams | Select-Object -First 1)
    if ($first.Count -gt 0) {
        return @{
            Stream      = $first[0]
            IsExplicit  = $false
        }
    }

    return @{
        Stream      = $null
        IsExplicit  = $false
    }
}

function Normalize-AudioLanguagePreferenceValue {
    param([string]$Value)

    $normalized = Convert-ToLowerInvariantSafe $Value
    switch -Regex ($normalized) {
        '^(|und|unknown|undefined)$' { return 'und' }
        '^(eng|en|english)$'         { return 'eng' }
        '^(jpn|ja|japanese)$'        { return 'jpn' }
        '^(spa|es|spanish)$'         { return 'spa' }
        '^(fre|fra|fr|french)$'      { return 'fra' }
        '^(ger|deu|de|german)$'      { return 'deu' }
        '^(ita|it|italian)$'         { return 'ita' }
        '^(por|pt|portuguese)$'      { return 'por' }
        '^(rus|ru|russian)$'         { return 'rus' }
        '^(kor|ko|korean)$'          { return 'kor' }
        '^(chi|zho|zh|chinese)$'     { return 'zho' }
        default                      { return $normalized }
    }
}

function Get-NormalizedPreferredAudioLanguages {
    $preferred = @(
        $script:PreferredDefaultAudioLanguages |
            ForEach-Object { Normalize-AudioLanguagePreferenceValue ([string]$_) } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            Select-Object -Unique
    )
    if ($preferred.Count -eq 0) { return @('eng') }
    return $preferred
}

function Test-AudioTitleLooksLikeCommentary {
    param([string]$Title)

    if ([string]::IsNullOrWhiteSpace($Title)) { return $false }
    return ($Title -match '(?i)commentary|director|cast|audio\s*description|descriptive|behind.the.scenes|isolated\s*score')
}

function Get-AudioCodecFidelityRank {
    param([string]$Codec)

    switch (Convert-ToLowerInvariantSafe $Codec) {
        'truehd'     { return 130 }
        'mlp'        { return 125 }
        'dts-hd'     { return 120 }
        'dts_hd_ma'  { return 120 }
        'flac'       { return 115 }
        'alac'       { return 112 }
        'pcm_s24le'  { return 110 }
        'pcm_s24be'  { return 110 }
        'pcm_s16le'  { return 108 }
        'pcm_s16be'  { return 108 }
        'dts'        { return 100 }
        'eac3'       { return 90 }
        'ac3'        { return 82 }
        'opus'       { return 76 }
        'aac'        { return 72 }
        'vorbis'     { return 68 }
        'mp3'        { return 60 }
        default      { return 50 }
    }
}

function Get-AudioStreamFidelityScore {
    param($Stream)

    $channels = 0
    [void][int]::TryParse([string](Get-TagValue -Object $Stream -Name 'channels'), [ref]$channels)
    if ($channels -lt 0) { $channels = 0 }
    $channels = [math]::Min($channels, 16)

    $codecRank = Get-AudioCodecFidelityRank (Get-TagValue -Object $Stream -Name 'codec_name')
    return (($codecRank * 1000) + ($channels * 10))
}

function Get-ExpectedDefaultAudioCandidate {
    param([array]$Streams)

    if ($null -eq $Streams -or $Streams.Count -eq 0) { return $null }

    $preferred = Get-NormalizedPreferredAudioLanguages
    $candidates = [System.Collections.Generic.List[object]]::new()

    for ($i = 0; $i -lt $Streams.Count; $i++) {
        $stream = $Streams[$i]
        $lang = Normalize-AudioLanguagePreferenceValue (Get-StreamTagValue -Stream $stream -Name 'language')
        $title = Get-StreamTagValue -Stream $stream -Name 'title'
        $preferenceRank = $preferred.IndexOf($lang)
        if ($preferenceRank -lt 0) { $preferenceRank = [int]::MaxValue }

        $candidates.Add([pscustomobject]@{
            Stream         = $stream
            Index          = $i
            NormalizedLang = $lang
            Title          = $title
            IsCommentary   = (Test-AudioTitleLooksLikeCommentary $title)
            FidelityScore  = Get-AudioStreamFidelityScore $stream
            PreferenceRank = $preferenceRank
        }) | Out-Null
    }

    $pool = @($candidates | Where-Object { -not $_.IsCommentary })
    if ($pool.Count -eq 0) {
        $pool = @($candidates)
    }

    $preferredPool = @($pool | Where-Object { $_.PreferenceRank -lt [int]::MaxValue })
    if ($preferredPool.Count -gt 0) {
        $pool = $preferredPool
    }

    return ($pool | Sort-Object `
        @{ Expression = { $_.PreferenceRank } }, `
        @{ Expression = { $_.FidelityScore }; Descending = $true }, `
        @{ Expression = { $_.Index } } |
        Select-Object -First 1)
}

function Format-AudioCandidateLabel {
    param($Candidate)

    if (-not $Candidate) { return 'unknown audio track' }

    $stream = $Candidate.Stream
    $lang = if ($Candidate.NormalizedLang) { $Candidate.NormalizedLang } else { 'und' }
    $codec = Convert-ToLowerInvariantSafe (Get-TagValue -Object $stream -Name 'codec_name')
    $channels = Get-TagValue -Object $stream -Name 'channels'
    $title = $Candidate.Title

    $parts = @($lang)
    if ($codec) { $parts += $codec }
    if ($channels) { $parts += "$channels" + 'ch' }
    if (-not [string]::IsNullOrWhiteSpace($title)) {
        $parts += "'$title'"
    }
    return ($parts -join ' | ')
}

function New-AuditResult {
    param(
        $FileInfo,
        [string]$RelativePath
    )

    return [pscustomobject]@{
        Path                    = $FileInfo.FullName
        SourceRoot              = $script:LibraryRootResolved
        RelativePath            = $RelativePath
        FileName                = $FileInfo.Name
        MediaType               = ''
        LookupTitle             = ''
        SizeBytes               = [int64]$FileInfo.Length
        SizeGB                  = [math]::Round(($FileInfo.Length / 1GB), 3)
        Extension               = $FileInfo.Extension
        Bucket                  = 'OK'
        BucketRank              = 0
        DurationSeconds         = 0.0
        Container               = ''
        VideoCodecs             = @()
        AudioCodecs             = @()
        SubtitleCodecs          = @()
        AudioCount              = 0
        SubtitleCount           = 0
        Tx3gSubtitleCount       = 0
        Tx3gEmbeddedSrtCount    = 0
        Tx3gEmbeddedSrtRecords  = @()
        Tx3gEmbeddedSrtInvalidCount = 0
        Tx3gExternalSrtCount    = 0
        Tx3gExternalSrtFiles    = @()
        Tx3gSidecarSrtFiles     = @()
        Tx3gSidecarSrtInvalidCount = 0
        Tx3gSidecarFailureCount = 0
        BdpgsSubtitleCount      = 0
        BdpgsEmbeddedSrtCount   = 0
        BdpgsEmbeddedSrtRecords = @()
        BdpgsEmbeddedSrtInvalidCount = 0
        BdpgsSidecarFailureCount = 0
        VobSubSubtitleCount      = 0
        VobSubEmbeddedSrtCount   = 0
        VobSubEmbeddedSrtRecords = @()
        VobSubEmbeddedSrtInvalidCount = 0
        VobSubSidecarFailureCount = 0
        DefaultAudioCodec       = 'none'
        DefaultAudioLanguage    = 'none'
        DefaultAudioTitle       = ''
        DefaultSubtitleCodec    = 'none'
        DefaultSubtitleLanguage = 'none'
        DefaultSubtitleTitle    = ''
        HasEnglishAudio         = $false
        HasEnglishSubtitle      = $false
        HasTextSubtitle         = $false
        SidecarPath             = ''
        SidecarVersion          = ''
        SidecarRoute            = ''
        Issues                  = [System.Collections.Generic.List[object]]::new()
    }
}

function Add-AuditIssue {
    param(
        $Result,
        [ValidateSet('REVIEW','RERUN_PIPELINE','REDOWNLOAD_CANDIDATE')] [string] $Bucket,
        [string] $Code,
        [string] $Message,
        [string] $SuggestedAction = ''
    )

    $Result.Issues.Add([pscustomobject]@{
        Bucket          = $Bucket
        Code            = $Code
        Message         = $Message
        SuggestedAction = $SuggestedAction
    }) | Out-Null

    $newRank = Get-BucketRank $Bucket
    if ($newRank -gt $Result.BucketRank) {
        $Result.Bucket = $Bucket
        $Result.BucketRank = $newRank
    }
}
