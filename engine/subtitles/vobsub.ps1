# ==============================================================================
# engine\subtitles\vobsub.ps1
# ==============================================================================
# VobSub/DVD bitmap subtitle detection, Matroska extraction, sidecar pairing,
# OCR tool resolution, and OCR conversion to SRT.
# Dot-sourced by engine\subtitles\subtitles.ps1; preserves script-scope config.
# ==============================================================================

if (-not (Get-Command -Name Write-SubtitleTrackProgress -ErrorAction SilentlyContinue)) {
    function Write-SubtitleTrackProgress {
        param(
            [string]$Kind,
            [int]$StreamIndex = -1,
            [string]$Stage,
            [string]$Status,
            [int]$StepIndex = 0,
            [int]$StepTotal = 4,
            [array]$Steps = @(),
            [string]$Detail = "",
            [object]$CueCount = $null,
            [switch]$Completed,
            [switch]$Failed
        )
    }
}

function Test-IsVobSubSubtitleStream {
    param($Stream)

    if (-not $Stream) { return $false }
    $codec = if ($Stream.codec_name) { ([string]$Stream.codec_name).ToLowerInvariant() } else { "" }
    $tag   = if ($Stream.codec_tag_string) { ([string]$Stream.codec_tag_string).ToLowerInvariant() } else { "" }
    $long  = if ($Stream.codec_long_name) { ([string]$Stream.codec_long_name).ToLowerInvariant() } else { "" }

    if ($codec -in (Get-MediaSubtitleCodecVobSubNames)) { return $true }
    if ($tag -match 's_vobsub|vobsub|dvd') { return $true }
    if ($long -match 'vobsub|dvd\s+subtitle') { return $true }
    return $false
}

function Test-CanPreserveVobSubInFfmpegOutput {
    $container = Get-ConfiguredOutputContainerName
    return ($container -in (Get-MediaContainerMatroskaFamilyNames))
}

function Resolve-VobSubOcrLanguage {
    param([string]$Language)

    $normalized = Get-NormalizedSubtitleLanguage $Language
    $map = @{
        'eng' = 'eng'; 'en' = 'eng'; 'und' = 'eng'; '' = 'eng'
        'jpn' = 'jpn'; 'ja' = 'jpn'
        'spa' = 'spa'; 'es' = 'spa'
        'fre' = 'fra'; 'fra' = 'fra'; 'fr' = 'fra'
        'ger' = 'deu'; 'deu' = 'deu'; 'de' = 'deu'
        'ita' = 'ita'; 'it' = 'ita'
        'por' = 'por'; 'pt' = 'por'
        'rus' = 'rus'; 'ru' = 'rus'
        'chi' = 'chi_sim'; 'zho' = 'chi_sim'; 'zh' = 'chi_sim'
        'kor' = 'kor'; 'ko' = 'kor'
    }
    if ($map.ContainsKey($normalized)) { return $map[$normalized] }
    return $normalized
}

function Resolve-VobSubOcrToolInvocation {
    $toolPath = if ($script:VobSubOcrToolPath) { ([string]$script:VobSubOcrToolPath).Trim() } else { '' }
    if ([string]::IsNullOrWhiteSpace($toolPath)) {
        return [pscustomobject]@{ Ok = $false; FilePath = ''; PrefixArgs = @(); Reason = 'VobSubOcrToolPath is not configured' }
    }

    $resolved = $toolPath
    if (-not [System.IO.Path]::IsPathRooted($resolved)) {
        $baseDir = if ($scriptDir) { $scriptDir } elseif ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { (Get-Location).Path }
        $candidate = Join-Path $baseDir $resolved
        if (Test-Path -LiteralPath $candidate -ErrorAction SilentlyContinue) {
            $resolved = (Resolve-Path -LiteralPath $candidate).Path
        } elseif ($script:AllowSystemTools) {
            $cmd = Get-Command $resolved -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($cmd -and $cmd.Source) { $resolved = $cmd.Source }
        }
    }

    if (-not (Test-Path -LiteralPath $resolved -ErrorAction SilentlyContinue) -and -not (Get-Command $resolved -ErrorAction SilentlyContinue)) {
        return [pscustomobject]@{ Ok = $false; FilePath = ''; PrefixArgs = @(); Reason = "VobSub OCR tool not found: $toolPath" }
    }

    if ([System.IO.Path]::GetExtension($resolved).Equals('.dll', [System.StringComparison]::OrdinalIgnoreCase)) {
        $dotnet = Get-Command dotnet -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not ($dotnet -and $dotnet.Source)) {
            return [pscustomobject]@{ Ok = $false; FilePath = ''; PrefixArgs = @(); Reason = 'VobSubOcrToolPath points to a .dll but dotnet was not found on PATH' }
        }
        return [pscustomobject]@{ Ok = $true; FilePath = $dotnet.Source; PrefixArgs = @($resolved); Reason = 'ok' }
    }

    return [pscustomobject]@{ Ok = $true; FilePath = $resolved; PrefixArgs = @(); Reason = 'ok' }
}

function Resolve-VobSubTesseractInvocation {
    param([string]$OcrToolPath = '')

    $candidateRoots = @()
    if (-not [string]::IsNullOrWhiteSpace($OcrToolPath)) {
        $toolDir = Split-Path -Parent $OcrToolPath
        if ($toolDir) {
            $candidateRoots += $toolDir
            $candidateRoots += (Join-Path $toolDir 'Tesseract550')
            $candidateRoots += (Join-Path $toolDir 'Tesseract-OCR')
            $candidateRoots += (Join-Path $toolDir 'Tesseract')
        }
    }

    $baseDir = if ($scriptDir) { $scriptDir } elseif ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { (Get-Location).Path }
    $candidateRoots += @(
        (Join-Path $baseDir 'Tools\SubtitleEdit\Tesseract550'),
        (Join-Path $baseDir 'Tools\SubtitleEdit\Tesseract-OCR'),
        (Join-Path $baseDir 'Tools\SubtitleEdit\Tesseract'),
        (Join-Path $baseDir 'Tools\Tesseract-OCR'),
        (Join-Path $baseDir 'Tools\Tesseract')
    )

    foreach ($root in @($candidateRoots | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Select-Object -Unique)) {
        $candidate = Join-Path ([string]$root) 'tesseract.exe'
        if (Test-Path -LiteralPath $candidate -PathType Leaf -ErrorAction SilentlyContinue) {
            $resolved = (Resolve-Path -LiteralPath $candidate).Path
            return [pscustomobject]@{ Ok = $true; FilePath = $resolved; Directory = (Split-Path -Parent $resolved); Reason = 'ok' }
        }
    }

    if (-not [bool]$script:AllowSystemTools) {
        return [pscustomobject]@{ Ok = $false; FilePath = ''; Directory = ''; Reason = 'tesseract was not found in bundled VobSub OCR tool paths, and AllowSystemTools is disabled' }
    }

    $cmd = Get-Command tesseract -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd -and $cmd.Source) {
        return [pscustomobject]@{ Ok = $true; FilePath = $cmd.Source; Directory = (Split-Path -Parent $cmd.Source); Reason = 'ok' }
    }
    return [pscustomobject]@{ Ok = $false; FilePath = ''; Directory = ''; Reason = 'tesseract was not found in bundled VobSub OCR tool paths or PATH' }
}

function Resolve-VobSubMkvextractPath {
    $configured = Get-Variable -Name mkvextractPath -Scope Script -ErrorAction SilentlyContinue
    if ($configured -and -not [string]::IsNullOrWhiteSpace([string]$configured.Value) -and (Test-Path -LiteralPath ([string]$configured.Value) -PathType Leaf -ErrorAction SilentlyContinue)) {
        return [pscustomobject]@{ Ok = $true; FilePath = [string]$configured.Value; Reason = 'ok' }
    }

    $mkvmerge = Get-Variable -Name mkvmergePath -Scope Script -ErrorAction SilentlyContinue
    if ($mkvmerge -and -not [string]::IsNullOrWhiteSpace([string]$mkvmerge.Value)) {
        $sibling = Join-Path (Split-Path ([string]$mkvmerge.Value) -Parent) 'mkvextract.exe'
        if (Test-Path -LiteralPath $sibling -PathType Leaf -ErrorAction SilentlyContinue) {
            return [pscustomobject]@{ Ok = $true; FilePath = (Resolve-Path -LiteralPath $sibling).Path; Reason = 'ok' }
        }
    }

    if (Get-Command -Name Resolve-BundledExecutable -ErrorAction SilentlyContinue) {
        $resolved = Resolve-BundledExecutable -CommandName 'mkvextract' -RelativeCandidates @('Tools\MKVToolNix\mkvextract.exe')
        if ($resolved) { return [pscustomobject]@{ Ok = $true; FilePath = $resolved; Reason = 'ok' } }
    }

    return [pscustomobject]@{ Ok = $false; FilePath = ''; Reason = 'mkvextract was not found in Tools\MKVToolNix or PATH' }
}

function New-VobSubFailureRecord {
    param(
        [hashtable]$Entry,
        [string]$Reason,
        [string]$ErrorCode = 'SUBTITLE_VOBSUB_OCR_FAILED',
        [string]$ReproPath = $null,
        [string]$ErrorText = $null
    )

    $streamIndex = if ($Entry -and $Entry.Stream) { [int]$Entry.Stream.index } else { -1 }
    $category = if ($ErrorCode -match 'TOOL_MISSING|TESSERACT_MISSING') { 'tool_missing' } else { 'subtitle_conversion' }
    $operation = if ($ErrorCode -match 'EXTRACT') { 'subtitle-vobsub-extract' } else { 'subtitle-vobsub-ocr' }
    return New-StandardFailureRecord -Stage $operation -Operation $operation -Category $category -Reason $Reason -ErrorCode $ErrorCode -Tool 'vobsub-ocr' -ReproPath $ReproPath -Retryable $true -AdditionalProperties @{
        StreamIndex     = $streamIndex
        stream_index    = $streamIndex
        SubtitleOrdinal = if ($Entry -and $Entry.ContainsKey('SubtitleOrdinal')) { $Entry.SubtitleOrdinal } else { $null }
        subtitle_ordinal = if ($Entry -and $Entry.ContainsKey('SubtitleOrdinal')) { $Entry.SubtitleOrdinal } else { $null }
        SourceKind      = if ($Entry -and $Entry.ContainsKey('SourceKind')) { $Entry.SourceKind } else { 'embedded' }
        source_kind     = if ($Entry -and $Entry.ContainsKey('SourceKind')) { $Entry.SourceKind } else { 'embedded' }
        IdxPath         = if ($Entry -and $Entry.ContainsKey('IdxPath')) { $Entry.IdxPath } else { '' }
        idx_path        = if ($Entry -and $Entry.ContainsKey('IdxPath')) { $Entry.IdxPath } else { '' }
        SubPath         = if ($Entry -and $Entry.ContainsKey('SubPath')) { $Entry.SubPath } else { '' }
        sub_path        = if ($Entry -and $Entry.ContainsKey('SubPath')) { $Entry.SubPath } else { '' }
        Language        = if ($Entry -and $Entry.ContainsKey('Lang')) { $Entry.Lang } else { 'und' }
        Title           = if ($Entry -and $Entry.ContainsKey('Title')) { $Entry.Title } else { '' }
        SourceIsDefault = if ($Entry -and $Entry.ContainsKey('SourceIsDefault')) { [bool]$Entry.SourceIsDefault } else { $false }
        source_is_default = if ($Entry -and $Entry.ContainsKey('SourceIsDefault')) { [bool]$Entry.SourceIsDefault } else { $false }
        IsForced        = if ($Entry -and $Entry.ContainsKey('IsForced')) { [bool]$Entry.IsForced } else { $false }
        is_forced       = if ($Entry -and $Entry.ContainsKey('IsForced')) { [bool]$Entry.IsForced } else { $false }
        ErrorText       = $ErrorText
        error_text      = $ErrorText
    }
}

function ConvertTo-VobSubEmbeddedSrtTrackRecords {
    param([array] $VobSubTracks)

    $records = [System.Collections.Generic.List[object]]::new()
    foreach ($track in @($VobSubTracks)) {
        if (-not $track) { continue }
        $entry = if ($track.StreamInfo) { $track.StreamInfo } else { $track }
        if (-not $entry) { continue }

        $records.Add([pscustomobject]@{
            source_kind              = if ($entry.ContainsKey('SourceKind')) { [string]$entry.SourceKind } else { 'embedded' }
            source_stream_index      = if ($entry.Stream) { [int]$entry.Stream.index } else { -1 }
            subtitle_ordinal         = if ($entry.ContainsKey('SubtitleOrdinal')) { $entry.SubtitleOrdinal } else { $null }
            language                 = if ($entry.ContainsKey('Lang')) { $entry.Lang } else { 'und' }
            title                    = if ($entry.ContainsKey('Title')) { $entry.Title } else { '' }
            raw_title                = if ($entry.ContainsKey('RawTitle')) { $entry.RawTitle } else { '' }
            idx_path                 = if ($entry.ContainsKey('IdxPath')) { $entry.IdxPath } else { '' }
            sub_path                 = if ($entry.ContainsKey('SubPath')) { $entry.SubPath } else { '' }
            cue_count                = if ($track.CueCount) { [int]$track.CueCount } else { 0 }
            is_default               = if ($entry.ContainsKey('IsDefault')) { [bool]$entry.IsDefault } else { $false }
            is_forced                = if ($entry.ContainsKey('IsForced')) { [bool]$entry.IsForced } else { $false }
            is_sdh                   = if ($entry.ContainsKey('IsSdh')) { [bool]$entry.IsSdh } else { $false }
            is_supplemental          = if ($entry.ContainsKey('IsSupplemental')) { [bool]$entry.IsSupplemental } else { $false }
            supplemental_forced      = if ($entry.ContainsKey('SupplementalForced')) { [bool]$entry.SupplementalForced } else { $false }
            original_preserved       = if ($track.ContainsKey('OriginalPreserved')) { [bool]$track.OriginalPreserved } else { $false }
            original_preserve_reason = if ($track.ContainsKey('OriginalPreserveReason')) { [string]$track.OriginalPreserveReason } else { '' }
        })
    }

    return @($records)
}

function Get-VobSubIdxLanguage {
    param([string]$IdxPath)

    if ([string]::IsNullOrWhiteSpace($IdxPath) -or -not (Test-Path -LiteralPath $IdxPath -PathType Leaf -ErrorAction SilentlyContinue)) {
        return 'und'
    }

    try {
        foreach ($line in @(Get-Content -LiteralPath $IdxPath -TotalCount 200 -ErrorAction Stop)) {
            $text = [string]$line
            if ($text -match '^\s*id:\s*([A-Za-z]{2,3})\s*,') {
                return (Get-NormalizedSubtitleLanguage $Matches[1])
            }
            if ($text -match '^\s*langidx:\s*([A-Za-z]{2,3})\s*$') {
                return (Get-NormalizedSubtitleLanguage $Matches[1])
            }
        }
    } catch {}

    return 'und'
}

function Find-VobSubSidecarPairs {
    param(
        [Parameter(Mandatory)] [string]$MediaPath,
        [string]$Context = ''
    )

    $pairs = [System.Collections.Generic.List[object]]::new()
    if ([string]::IsNullOrWhiteSpace($MediaPath) -or -not (Test-Path -LiteralPath $MediaPath -PathType Leaf -ErrorAction SilentlyContinue)) {
        return @()
    }

    $dir = Split-Path $MediaPath -Parent
    $mediaStem = [System.IO.Path]::GetFileNameWithoutExtension($MediaPath)
    if ([string]::IsNullOrWhiteSpace($dir) -or [string]::IsNullOrWhiteSpace($mediaStem)) { return @() }

    $idxFiles = @(Get-ChildItem -LiteralPath $dir -Filter "$mediaStem*.idx" -File -ErrorAction SilentlyContinue)
    foreach ($idx in $idxFiles) {
        $stem = [System.IO.Path]::GetFileNameWithoutExtension($idx.Name)
        $matchesMediaStem = ($stem -eq $mediaStem -or $stem.StartsWith("$mediaStem.", [System.StringComparison]::OrdinalIgnoreCase))
        if (-not $matchesMediaStem) { continue }

        $subPath = Join-Path $dir ($stem + '.sub')
        $hasSub = (Test-Path -LiteralPath $subPath -PathType Leaf -ErrorAction SilentlyContinue)
        $subLength = 0
        if ($hasSub) {
            try { $subLength = [long](Get-Item -LiteralPath $subPath -ErrorAction Stop).Length } catch { $subLength = 0 }
        }
        $language = Get-VobSubIdxLanguage -IdxPath $idx.FullName
        if ($language -eq 'und' -and $stem.Length -gt $mediaStem.Length) {
            $suffix = $stem.Substring($mediaStem.Length).TrimStart('.')
            $firstToken = @($suffix -split '[._ -]')[0]
            if ($firstToken -match '^[A-Za-z]{2,3}$') { $language = (Get-NormalizedSubtitleLanguage $firstToken) }
        }
        $title = if ($stem -eq $mediaStem) { 'VobSub' } else { ($stem.Substring($mediaStem.Length).TrimStart('.') -replace '[._]+', ' ') }
        if ([string]::IsNullOrWhiteSpace($title)) { $title = 'VobSub' }

        $pairs.Add([pscustomobject]@{
            Ok       = ($hasSub -and $subLength -gt 0)
            IdxPath  = $idx.FullName
            SubPath  = $subPath
            Stem     = $stem
            Language = $language
            Title    = $title
            Reason   = if (-not $hasSub) { 'matching .sub file is missing' } elseif ($subLength -le 0) { 'matching .sub file is empty' } else { 'ok' }
        }) | Out-Null
    }

    if ($pairs.Count -gt 0) {
        Write-Log "${Context}VobSub sidecars: found $($pairs.Count) .idx candidate(s) next to source" "DEBUG"
    }
    return @($pairs)
}

function New-VobSubSidecarSubtitleEntry {
    param(
        [Parameter(Mandatory)] $Pair,
        [int]$SubtitleOrdinal = 0
    )

    $language = if ($Pair.Language) { [string]$Pair.Language } else { 'und' }
    $title = if ($Pair.Title) { [string]$Pair.Title } else { 'VobSub' }
    $disposition = [pscustomobject]@{
        forced  = if ($title -match '(?i)\bforced\b') { 1 } else { 0 }
        default = 0
    }
    $stream = [pscustomobject]@{
        index            = -1
        codec_name       = 'vobsub'
        codec_long_name  = 'VobSub sidecar'
        codec_tag_string = 'S_VOBSUB'
        tags             = [pscustomobject]@{ language = $language; title = $title }
        disposition      = $disposition
    }
    $policy = Resolve-SubtitleStreamPolicy -Stream $stream -SubtitleOrdinal $SubtitleOrdinal
    $entry = New-SubtitleFilterEntry -Policy $policy
    $entry.SourceKind = 'sidecar'
    $entry.IdxPath = [string]$Pair.IdxPath
    $entry.SubPath = [string]$Pair.SubPath
    $entry.SidecarPairOk = [bool]$Pair.Ok
    $entry.SidecarPairReason = [string]$Pair.Reason
    $entry.Retain = [bool]$policy.Retain
    return $entry
}

function Resolve-VobSubMkvTrackId {
    param(
        [Parameter(Mandatory)] [string]$SourceFile,
        [Parameter(Mandatory)] [hashtable]$StreamInfo,
        [string]$Context = ''
    )

    $streamIndex = if ($StreamInfo -and $StreamInfo.Stream) { [int]$StreamInfo.Stream.index } else { -1 }
    if ($streamIndex -lt 0) {
        return [pscustomobject]@{ Ok = $false; TrackId = -1; Reason = 'VobSub stream index is not available' }
    }

    try {
        $probeTimeoutSeconds = Get-SubtitleOperationTimeoutSeconds -ScriptVariableName 'SubtitleProbeTimeoutSeconds' -DefaultSeconds 30
        $result = Invoke-MkvmergeCommand -ArgumentList @('-J', $SourceFile) -TimeoutSeconds $probeTimeoutSeconds -Stage 'subtitle-vobsub-mkv-identify' -SaveReproOnFailure
        if ($result.ExitCode -ne 0) {
            $reason = if ($result.Error) { Get-ErrorTextSummary -ErrorText $result.Error } else { "mkvmerge exited $($result.ExitCode)" }
            return [pscustomobject]@{ Ok = $false; TrackId = -1; Reason = $reason; ReproPath = $result.ReproPath; ErrorText = $result.Error }
        }
        $json = $result.Output | ConvertFrom-Json
        foreach ($track in @($json.tracks)) {
            if ($track.type -ne 'subtitles') { continue }
            $number = $track.properties.number
            if ($null -ne $number -and ([int]$number - 1) -eq $streamIndex) {
                return [pscustomobject]@{ Ok = $true; TrackId = [int]$track.id; Reason = 'ok'; ReproPath = ''; ErrorText = '' }
            }
        }
    } catch {
        return [pscustomobject]@{ Ok = $false; TrackId = -1; Reason = "mkvmerge JSON parse failed: $($_.Exception.Message)"; ReproPath = ''; ErrorText = '' }
    }

    return [pscustomobject]@{ Ok = $false; TrackId = -1; Reason = "Could not map ffprobe subtitle stream $streamIndex to an MKVToolNix track id"; ReproPath = ''; ErrorText = '' }
}

function Extract-VobSubToIdxSub {
    param(
        [Parameter(Mandatory)] [string]$SourceFile,
        [hashtable]$StreamInfo = @{},
        [string]$Context = ''
    )

    $sourceKind = if ($StreamInfo -and $StreamInfo.ContainsKey('SourceKind')) { [string]$StreamInfo.SourceKind } else { 'embedded' }
    $streamIndex = if ($StreamInfo -and $StreamInfo.Stream) { [int]$StreamInfo.Stream.index } else { -1 }

    if ($sourceKind -eq 'sidecar') {
        $idxPath = if ($StreamInfo.ContainsKey('IdxPath')) { [string]$StreamInfo.IdxPath } else { '' }
        $subPath = if ($StreamInfo.ContainsKey('SubPath')) { [string]$StreamInfo.SubPath } else { '' }
        if ([string]::IsNullOrWhiteSpace($idxPath) -or -not (Test-Path -LiteralPath $idxPath -PathType Leaf -ErrorAction SilentlyContinue)) {
            $reason = "VobSub .idx sidecar is missing: $idxPath"
            return [pscustomobject]@{ Ok = $false; IdxPath = $idxPath; SubPath = $subPath; TempFiles = @(); Reason = $reason; Failure = (New-VobSubFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_VOBSUB_PAIR_MISSING') }
        }
        if ([string]::IsNullOrWhiteSpace($subPath) -or -not (Test-Path -LiteralPath $subPath -PathType Leaf -ErrorAction SilentlyContinue) -or (Get-Item -LiteralPath $subPath -ErrorAction SilentlyContinue).Length -le 0) {
            $reason = "VobSub .sub sidecar is missing or empty for $idxPath"
            return [pscustomobject]@{ Ok = $false; IdxPath = $idxPath; SubPath = $subPath; TempFiles = @(); Reason = $reason; Failure = (New-VobSubFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_VOBSUB_PAIR_MISSING') }
        }
        return [pscustomobject]@{ Ok = $true; IdxPath = $idxPath; SubPath = $subPath; TempFiles = @(); Reason = 'ok'; Failure = $null }
    }

    $sourceExt = [System.IO.Path]::GetExtension($SourceFile).TrimStart('.').ToLowerInvariant()
    if ($sourceExt -notin (Get-MediaContainerMatroskaFamilyNames)) {
        $reason = "Embedded VobSub extraction is currently supported only for Matroska-family inputs; source extension is .$sourceExt"
        return [pscustomobject]@{ Ok = $false; IdxPath = ''; SubPath = ''; TempFiles = @(); Reason = $reason; Failure = (New-VobSubFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_VOBSUB_EXTRACT_UNSUPPORTED_CONTAINER') }
    }

    $mkvextract = Resolve-VobSubMkvextractPath
    if (-not $mkvextract.Ok) {
        return [pscustomobject]@{ Ok = $false; IdxPath = ''; SubPath = ''; TempFiles = @(); Reason = $mkvextract.Reason; Failure = (New-VobSubFailureRecord -Entry $StreamInfo -Reason $mkvextract.Reason -ErrorCode 'SUBTITLE_VOBSUB_EXTRACT_TOOL_MISSING') }
    }

    $trackId = Resolve-VobSubMkvTrackId -SourceFile $SourceFile -StreamInfo $StreamInfo -Context $Context
    if (-not $trackId.Ok) {
        return [pscustomobject]@{ Ok = $false; IdxPath = ''; SubPath = ''; TempFiles = @(); Reason = $trackId.Reason; Failure = (New-VobSubFailureRecord -Entry $StreamInfo -Reason $trackId.Reason -ErrorCode 'SUBTITLE_VOBSUB_EXTRACT_FAILED' -ReproPath $trackId.ReproPath -ErrorText $trackId.ErrorText) }
    }

    $idxPath = Join-Path $script:processingDir "sub_vobsub_$([guid]::NewGuid().ToString('N')).idx"
    $subPath = [System.IO.Path]::ChangeExtension($idxPath, '.sub')
    $args = @('tracks', $SourceFile, ('{0}:{1}' -f $trackId.TrackId, $idxPath))

    try {
        Write-SubtitleTrackProgress -Kind 'vobsub' -StreamIndex $streamIndex -Stage 'extract' -Status 'Extracting VobSub IDX/SUB' -StepIndex 1 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail ([System.IO.Path]::GetFileName($SourceFile))
        $timeoutSeconds = Get-SubtitleOperationTimeoutSeconds -ScriptVariableName 'SubtitleExtractTimeoutSeconds' -DefaultSeconds 180
        $result = Invoke-MkvextractCommand -FilePath $mkvextract.FilePath -ArgumentList $args -TimeoutSeconds $timeoutSeconds -Stage 'subtitle-vobsub-extract' -SaveReproOnFailure
        if ($result.ExitCode -ne 0) {
            $reason = if ($result.Error) { Get-ErrorTextSummary -ErrorText $result.Error } else { "mkvextract exited $($result.ExitCode)" }
            Write-SubtitleTrackProgress -Kind 'vobsub' -StreamIndex $streamIndex -Stage 'extract' -Status 'VobSub extraction failed' -StepIndex 1 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail $reason -Failed
            return [pscustomobject]@{ Ok = $false; IdxPath = $idxPath; SubPath = $subPath; TempFiles = @($idxPath, $subPath); Reason = $reason; Failure = (New-VobSubFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_VOBSUB_EXTRACT_FAILED' -ReproPath $result.ReproPath -ErrorText $result.Error) }
        }
        if (-not (Test-Path -LiteralPath $idxPath -PathType Leaf -ErrorAction SilentlyContinue) -or -not (Test-Path -LiteralPath $subPath -PathType Leaf -ErrorAction SilentlyContinue) -or (Get-Item -LiteralPath $subPath -ErrorAction SilentlyContinue).Length -le 0) {
            $reason = 'VobSub extraction produced no usable IDX/SUB pair'
            Write-SubtitleTrackProgress -Kind 'vobsub' -StreamIndex $streamIndex -Stage 'extract' -Status 'VobSub extraction failed' -StepIndex 1 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail $reason -Failed
            return [pscustomobject]@{ Ok = $false; IdxPath = $idxPath; SubPath = $subPath; TempFiles = @($idxPath, $subPath); Reason = $reason; Failure = (New-VobSubFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_VOBSUB_EXTRACT_FAILED') }
        }
        Write-SubtitleTrackProgress -Kind 'vobsub' -StreamIndex $streamIndex -Stage 'extract' -Status 'VobSub IDX/SUB extracted' -StepIndex 1 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail ([System.IO.Path]::GetFileName($idxPath))
        return [pscustomobject]@{ Ok = $true; IdxPath = $idxPath; SubPath = $subPath; TempFiles = @($idxPath, $subPath); Reason = 'ok'; Failure = $null }
    } catch {
        $reason = "VobSub extraction error: $($_.Exception.Message)"
        Write-SubtitleTrackProgress -Kind 'vobsub' -StreamIndex $streamIndex -Stage 'extract' -Status 'VobSub extraction failed' -StepIndex 1 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail $reason -Failed
        return [pscustomobject]@{ Ok = $false; IdxPath = $idxPath; SubPath = $subPath; TempFiles = @($idxPath, $subPath); Reason = $reason; Failure = (New-VobSubFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_VOBSUB_EXTRACT_FAILED') }
    }
}

function Convert-VobSubToSrt {
    param(
        [Parameter(Mandatory)] [string]$SourceFile,
        [int]$StreamIndex = -1,
        [hashtable]$StreamInfo = @{},
        [Parameter(Mandatory)] [string]$DestinationPath,
        [string]$Context = ""
    )

    if ($StreamIndex -lt 0 -and $StreamInfo -and $StreamInfo.Stream) { $StreamIndex = [int]$StreamInfo.Stream.index }
    $ocrTempSrt = $null
    $extract = $null
    try {
        $extract = Extract-VobSubToIdxSub -SourceFile $SourceFile -StreamInfo $StreamInfo -Context $Context
        if (-not $extract.Ok) { return $extract }

        $tool = Resolve-VobSubOcrToolInvocation
        if (-not $tool.Ok) {
            Write-SubtitleTrackProgress -Kind 'vobsub' -StreamIndex $StreamIndex -Stage 'convert_ocr' -Status 'VobSub OCR setup failed' -StepIndex 2 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail $tool.Reason -Failed
            return [pscustomobject]@{ Ok = $false; Path = $null; CueCount = 0; Reason = $tool.Reason; Failure = (New-VobSubFailureRecord -Entry $StreamInfo -Reason $tool.Reason -ErrorCode 'SUBTITLE_VOBSUB_OCR_TOOL_MISSING') }
        }

        $tesseract = Resolve-VobSubTesseractInvocation -OcrToolPath $tool.FilePath
        if (-not $tesseract.Ok) {
            Write-SubtitleTrackProgress -Kind 'vobsub' -StreamIndex $StreamIndex -Stage 'convert_ocr' -Status 'VobSub OCR setup failed' -StepIndex 2 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail $tesseract.Reason -Failed
            return [pscustomobject]@{ Ok = $false; Path = $null; CueCount = 0; Reason = $tesseract.Reason; Failure = (New-VobSubFailureRecord -Entry $StreamInfo -Reason $tesseract.Reason -ErrorCode 'SUBTITLE_VOBSUB_TESSERACT_MISSING') }
        }

        $ocrLanguage = Resolve-VobSubOcrLanguage -Language $StreamInfo.Lang
        $ocrTempSrt = New-SrtAtomicTempPath -DestinationPath $DestinationPath
        $outputFolder = Split-Path $ocrTempSrt -Parent
        $outputFile = Split-Path $ocrTempSrt -Leaf
        $ocrArgs = [System.Collections.Generic.List[string]]::new()
        $ocrArgs.AddRange([string[]]@($tool.PrefixArgs))
        $ocrArgs.AddRange([string[]]@(
            [string]$extract.IdxPath,
            'subrip',
            '--ocr-engine:tesseract',
            "--ocr-language:$ocrLanguage",
            "--output-folder:$outputFolder",
            "--output-filename:$outputFile",
            '--overwrite',
            '--json'
        ))

        try {
            $timeoutSeconds = Get-SubtitleOperationTimeoutSeconds -ScriptVariableName 'VobSubOcrTimeoutSeconds' -DefaultSeconds 1800
            $ocrPriority = if (Get-Variable -Name CpuEncodeProcessPriority -Scope Script -ErrorAction SilentlyContinue) {
                [string]$script:CpuEncodeProcessPriority
            } else { 'belownormal' }
            $ocrCpuLock = $null
            if (Get-Command -Name Acquire-CpuEncodeMutex -ErrorAction SilentlyContinue) {
                $ocrCpuLock = Acquire-CpuEncodeMutex -TimeoutSeconds 0
                if (-not $ocrCpuLock.Acquired) {
                    Write-Log "${Context}VobSub OCR: another CPU-bound job is running; waiting for slot ($($ocrCpuLock.Reason))" "WARN"
                    $ocrCpuLock = Acquire-CpuEncodeMutex -TimeoutSeconds $timeoutSeconds
                }
            }
            $oldPath = $env:PATH
            try {
                if ($tesseract.Directory -and (Test-Path -LiteralPath ([string]$tesseract.Directory) -PathType Container -ErrorAction SilentlyContinue)) {
                    $env:PATH = "$($tesseract.Directory);$oldPath"
                }
                Write-SubtitleTrackProgress -Kind 'vobsub' -StreamIndex $StreamIndex -Stage 'convert_ocr' -Status 'Running VobSub OCR' -StepIndex 2 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail ([System.IO.Path]::GetFileName($extract.IdxPath))
                $result = Invoke-VobSubOcrCommand -FilePath $tool.FilePath -ArgumentList @($ocrArgs.ToArray()) -TimeoutSeconds $timeoutSeconds -Stage 'subtitle-vobsub-ocr' -SaveReproOnFailure -ProcessPriority $ocrPriority
            } finally {
                $env:PATH = $oldPath
                if ($ocrCpuLock -and $ocrCpuLock.Acquired) { & $ocrCpuLock.Release }
            }

            if ($result.ExitCode -ne 0) {
                $reason = if ($result.Error) { Get-ErrorTextSummary -ErrorText $result.Error } else { "OCR tool exited $($result.ExitCode)" }
                Write-SubtitleTrackProgress -Kind 'vobsub' -StreamIndex $StreamIndex -Stage 'convert_ocr' -Status 'VobSub OCR failed' -StepIndex 2 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail $reason -Failed
                return [pscustomobject]@{ Ok = $false; Path = $null; CueCount = 0; Reason = $reason; Failure = (New-VobSubFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_VOBSUB_OCR_FAILED' -ReproPath $result.ReproPath -ErrorText $result.Error) }
            }

            Write-SubtitleTrackProgress -Kind 'vobsub' -StreamIndex $StreamIndex -Stage 'validate' -Status 'Validating VobSub OCR SRT' -StepIndex 3 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail ([System.IO.Path]::GetFileName($ocrTempSrt))
            $preMoveValidation = Test-SrtFileUsable -Path $ocrTempSrt
            if (-not $preMoveValidation.Ok) {
                $reason = "VobSub OCR SRT is not usable: $($preMoveValidation.Reason)"
                Write-SubtitleTrackProgress -Kind 'vobsub' -StreamIndex $StreamIndex -Stage 'validate' -Status 'VobSub OCR validation failed' -StepIndex 3 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail $reason -Failed
                return [pscustomobject]@{ Ok = $false; Path = $null; CueCount = 0; Reason = $reason; Failure = (New-VobSubFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_VOBSUB_OCR_EMPTY') }
            }
            $validation = Complete-AtomicSrtWrite -TempPath $ocrTempSrt -DestinationPath $DestinationPath
            Write-Log "${Context}VobSub->SRT: stream $StreamIndex -> $($validation.CueCount) cue(s)"
            Write-SubtitleTrackProgress -Kind 'vobsub' -StreamIndex $StreamIndex -Stage 'validate' -Status 'VobSub OCR SRT validated' -StepIndex 3 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail "$($validation.CueCount) cue(s)" -CueCount $validation.CueCount
            return [pscustomobject]@{ Ok = $true; Path = $DestinationPath; CueCount = $validation.CueCount; Reason = 'ok'; Failure = $null }
        } catch {
            $reason = "VobSub OCR error: $($_.Exception.Message)"
            Write-SubtitleTrackProgress -Kind 'vobsub' -StreamIndex $StreamIndex -Stage 'convert_ocr' -Status 'VobSub OCR failed' -StepIndex 2 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail $reason -Failed
            return [pscustomobject]@{ Ok = $false; Path = $null; CueCount = 0; Reason = $reason; Failure = (New-VobSubFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_VOBSUB_OCR_FAILED') }
        }
    } catch {
        $reason = "VobSub conversion error: $($_.Exception.Message)"
        Write-SubtitleTrackProgress -Kind 'vobsub' -StreamIndex $StreamIndex -Stage 'convert_ocr' -Status 'VobSub conversion failed' -StepIndex 2 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail $reason -Failed
        return [pscustomobject]@{ Ok = $false; Path = $null; CueCount = 0; Reason = $reason; Failure = (New-VobSubFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_VOBSUB_OCR_FAILED') }
    } finally {
        if ($extract -and $extract.TempFiles) {
            foreach ($path in @($extract.TempFiles)) {
                if (-not [string]::IsNullOrWhiteSpace([string]$path) -and (Test-Path -LiteralPath $path -ErrorAction SilentlyContinue)) {
                    Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
                }
            }
        }
        if ($ocrTempSrt -and (Test-Path -LiteralPath $ocrTempSrt -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $ocrTempSrt -Force -ErrorAction SilentlyContinue
        }
    }
}
