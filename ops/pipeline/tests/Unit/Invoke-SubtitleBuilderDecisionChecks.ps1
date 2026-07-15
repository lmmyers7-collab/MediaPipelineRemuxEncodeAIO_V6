[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Subtitle builder decision checks require PowerShell 7. Install pwsh or use the bundled runtime."
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

function Assert-ContainsText {
    param([string] $Text, [string] $Expected, [string] $Message)
    if ($Text -notlike "*$Expected*") { throw "$Message Text was '$Text'." }
}

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
    $script:LogRows.Add([pscustomobject]@{ Message = $Message; Level = $Level }) | Out-Null
}

function DebugLog {
    param([string] $Message)
    Write-Log -Message $Message -Level 'DEBUG'
}

function Get-EffectiveSubtitleSwitch {
    param([string] $Name, [bool] $Default)
    if ($script:SubtitleSwitches.ContainsKey($Name)) {
        return [bool]$script:SubtitleSwitches[$Name]
    }
    return [bool]$Default
}

function Get-ConfiguredOutputContainerName {
    return [string]$script:OutputContainer
}

function Test-SubtitleEntryLanguageIsPreferredDefault {
    param($Entry)
    return ([string]$Entry.Lang -eq [string]$script:PreferredSubtitleLanguage)
}

function Test-SubtitleEntryLanguageIsFallbackDefault {
    param($Entry)
    $lang = [string]$Entry.Lang
    return ([string]::IsNullOrWhiteSpace($lang) -or $lang -eq 'und')
}

function Test-IsTx3gSubtitleStream {
    param($Stream)
    $codec = if ($Stream.codec_name) { ([string]$Stream.codec_name).ToLowerInvariant() } else { '' }
    return ($codec -in @('mov_text', 'tx3g'))
}

function Test-IsBdpgsSubtitleStream {
    param($Stream)
    $codec = if ($Stream.codec_name) { ([string]$Stream.codec_name).ToLowerInvariant() } else { '' }
    return ($codec -in @('hdmv_pgs_subtitle', 'pgs'))
}

function Test-IsVobSubSubtitleStream {
    param($Stream)
    $codec = if ($Stream.codec_name) { ([string]$Stream.codec_name).ToLowerInvariant() } else { '' }
    return ($codec -in @('dvd_subtitle', 'vobsub'))
}

function Get-SubtitleLanguageDisplayMap {
    return @{
        eng = 'English'
        jpn = 'Japanese'
        und = 'Undefined'
    }
}

function Get-NormalizedSubtitleLanguage {
    param([string] $Language)
    if ([string]::IsNullOrWhiteSpace($Language)) { return 'und' }
    return $Language.Trim().ToLowerInvariant()
}

function Test-SubtitleTitleMatchesAnyKeyword {
    param([string] $TitleLower, [array] $Keywords)
    foreach ($keyword in @($Keywords)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$keyword) -and $TitleLower -match [regex]::Escape([string]$keyword)) {
            return $true
        }
    }
    return $false
}

function Get-SubtitleLanguagePolicy {
    param(
        [switch] $IsTx3g,
        [switch] $IsBdpgs,
        [switch] $IsVobSub,
        [switch] $IsAss
    )
    if ($script:SubtitleLanguagePolicy) { return @($script:SubtitleLanguagePolicy) }
    return @('eng')
}

function Get-ConvertedSrtCodecForFfmpegOutput {
    if ($script:ConvertedSrtCodec) { return [string]$script:ConvertedSrtCodec }
    return 'srt'
}

function Resolve-SubtitleConfiguredPath {
    param(
        [string] $PathValue,
        [switch] $AllowCommandLookup
    )
    return [string]$PathValue
}

function Test-CanPreserveTx3gInFfmpegOutput {
    return [bool]$script:CanPreserveTx3g
}

function Test-CanPreserveBdpgsInFfmpegOutput {
    return [bool]$script:CanPreserveBdpgs
}

function Test-CanPreserveVobSubInFfmpegOutput {
    return [bool]$script:CanPreserveVobSub
}

function New-Tx3gFailureRecord {
    param($Entry, [string] $Reason, [string] $ErrorCode, [string] $ReproPath, [string] $ErrorText)
    return [pscustomobject]@{
        error_code  = $ErrorCode
        ErrorCode   = $ErrorCode
        reason      = $Reason
        stream_index = $Entry.Stream.index
        ReproPath   = $ReproPath
        ErrorText   = $ErrorText
    }
}

function New-BdpgsFailureRecord {
    param($Entry, [string] $Reason, [string] $ErrorCode, [string] $ReproPath, [string] $ErrorText)
    return [pscustomobject]@{
        error_code  = $ErrorCode
        ErrorCode   = $ErrorCode
        reason      = $Reason
        stream_index = $Entry.Stream.index
        ReproPath   = $ReproPath
        ErrorText   = $ErrorText
    }
}

function New-VobSubFailureRecord {
    param($Entry, [string] $Reason, [string] $ErrorCode, [string] $ReproPath, [string] $ErrorText)
    return [pscustomobject]@{
        error_code  = $ErrorCode
        ErrorCode   = $ErrorCode
        reason      = $Reason
        stream_index = if ($Entry.Stream) { $Entry.Stream.index } else { -1 }
        ReproPath   = $ReproPath
        ErrorText   = $ErrorText
    }
}

function New-StandardFailureRecord {
    param(
        [string] $Stage,
        [string] $Operation,
        [string] $Category,
        [string] $Reason,
        [string] $ErrorCode,
        [string] $Tool,
        [string] $ReproPath,
        [bool] $Retryable,
        [hashtable] $AdditionalProperties = @{}
    )
    $record = [ordered]@{
        Stage      = $Stage
        Operation  = $Operation
        Category   = $Category
        Reason     = $Reason
        ErrorCode  = $ErrorCode
        error_code = $ErrorCode
        Tool       = $Tool
        ReproPath  = $ReproPath
        Retryable  = $Retryable
    }
    foreach ($key in $AdditionalProperties.Keys) { $record[$key] = $AdditionalProperties[$key] }
    return [pscustomobject]$record
}

function New-TestSubtitleEntry {
    param(
        [int] $Index,
        [string] $Lang,
        [string] $Title,
        [string] $Codec = 'subrip',
        [switch] $Supplemental,
        [switch] $Forced,
        [switch] $Tx3g,
        [switch] $Bdpgs,
        [switch] $VobSub,
        [string] $SourceKind = 'embedded',
        [switch] $SourceDefault,
        [bool] $LanguagePolicyMatched = $true,
        [string] $RetainReason = 'language_policy'
    )
    return @{
        Stream = [pscustomobject]@{ index = $Index }
        Lang = $Lang
        Title = $Title
        Codec = $Codec
        CodecTagString = ''
        RawTitle = $Title
        IsSupplemental = [bool]$Supplemental
        IsForced = [bool]$Forced
        IsTx3g = [bool]$Tx3g
        IsBdpgs = [bool]$Bdpgs
        IsVobSub = [bool]$VobSub
        IsDefault = [bool]$SourceDefault
        SourceIsDefault = [bool]$SourceDefault
        LanguagePolicyMatched = [bool]$LanguagePolicyMatched
        RetainReason = $RetainReason
        SourceKind = $SourceKind
    }
}

function Write-TestSrt {
    param([string] $Path, [string] $Text)
    [System.IO.File]::WriteAllText($Path, "1`r`n00:00:00,000 --> 00:00:01,000`r`n$Text`r`n", [System.Text.UTF8Encoding]::new($false))
}

function Convert-AssToSrt {
    param([string] $SourceFile, [int] $StreamIndex, $StreamInfo)
    $script:ConversionCalls.Add("ass:$StreamIndex") | Out-Null
    if ($script:AssConversionMode -eq 'fail') {
        return [pscustomobject]@{
            Ok = $false
            Reason = 'ass conversion failed'
            Failure = [pscustomobject]@{ error_code = 'SUBTITLE_ASS_CONVERT_FAILED'; ErrorCode = 'SUBTITLE_ASS_CONVERT_FAILED'; reason = 'ass conversion failed'; StreamIndex = $StreamIndex }
        }
    }
    $path = Join-Path $script:processingDir "ass_$StreamIndex.srt"
    Write-TestSrt -Path $path -Text "ASS $StreamIndex"
    return [pscustomobject]@{ Ok = $true; Path = $path; CueCount = 1 }
}

function Convert-Tx3gToSrt {
    param([string] $SourceFile, [int] $StreamIndex, $StreamInfo, [string] $DestinationPath, [string] $Context)
    $script:ConversionCalls.Add("tx3g:$StreamIndex") | Out-Null
    if ($script:Tx3gConversionMode -eq 'fail') {
        return [pscustomobject]@{
            Ok = $false
            Reason = 'tx3g extraction failed'
            ErrorCode = 'SUBTITLE_TX3G_EXTRACT_FAILED'
            Failure = [pscustomobject]@{ error_code = 'SUBTITLE_TX3G_EXTRACT_FAILED'; ErrorCode = 'SUBTITLE_TX3G_EXTRACT_FAILED'; reason = 'tx3g extraction failed'; StreamIndex = $StreamIndex }
        }
    }
    Write-TestSrt -Path $DestinationPath -Text "TX3G $StreamIndex"
    return [pscustomobject]@{ Ok = $true; Path = $DestinationPath; CueCount = 1 }
}

function Convert-BdpgsToSrt {
    param([string] $SourceFile, [int] $StreamIndex, $StreamInfo, [string] $DestinationPath, [string] $Context)
    $script:ConversionCalls.Add("bdpgs:$StreamIndex") | Out-Null
    if ($script:BdpgsConversionMode -eq 'fail') {
        return [pscustomobject]@{
            Ok = $false
            Reason = 'bdpgs ocr failed'
            Failure = [pscustomobject]@{ error_code = 'SUBTITLE_BDPGS_OCR_FAILED'; ErrorCode = 'SUBTITLE_BDPGS_OCR_FAILED'; reason = 'bdpgs ocr failed'; StreamIndex = $StreamIndex }
        }
    }
    Write-TestSrt -Path $DestinationPath -Text "BDPGS $StreamIndex"
    return [pscustomobject]@{ Ok = $true; Path = $DestinationPath; CueCount = 1 }
}

function Convert-VobSubToSrt {
    param([string] $SourceFile, [int] $StreamIndex, $StreamInfo, [string] $DestinationPath, [string] $Context)
    $script:ConversionCalls.Add("vobsub:$StreamIndex") | Out-Null
    if ($script:VobSubConversionMode -eq 'fail') {
        return [pscustomobject]@{
            Ok = $false
            Reason = 'vobsub ocr failed'
            Failure = [pscustomobject]@{ error_code = 'SUBTITLE_VOBSUB_OCR_FAILED'; ErrorCode = 'SUBTITLE_VOBSUB_OCR_FAILED'; reason = 'vobsub ocr failed'; StreamIndex = $StreamIndex }
        }
    }
    Write-TestSrt -Path $DestinationPath -Text "VobSub $StreamIndex"
    return [pscustomobject]@{ Ok = $true; Path = $DestinationPath; CueCount = 1 }
}

function Invoke-FFprobeCommand {
    param([array] $ArgumentList, [int] $TimeoutSeconds, [string] $Stage)
    $script:SubtitleProbeArgumentList = @($ArgumentList)
    $showEntriesIndex = [array]::IndexOf($ArgumentList, '-show_entries')
    $showEntries = if ($showEntriesIndex -ge 0) { [string]$ArgumentList[$showEntriesIndex + 1] } else { '' }
    $stream = [ordered]@{
        index = 3
        codec_name = 'subrip'
        codec_long_name = 'SubRip subtitle'
        codec_tag_string = ''
        codec_tag = '0x0000'
        tags = [ordered]@{ language = 'eng'; title = 'Forced' }
    }
    # Mirror current ffprobe behavior: disposition fields are emitted only
    # when the stream_disposition section is requested explicitly.
    if ($showEntries -match 'stream_disposition=default,forced') {
        $stream['disposition'] = [ordered]@{ default = 0; forced = 1 }
    }
    return [pscustomobject]@{
        ExitCode = 0
        Output = (@{ streams = @([pscustomobject]$stream) } | ConvertTo-Json -Depth 6 -Compress)
        Error = ''
    }
}

function Get-FileOverrideSubtitleSettings { return @{} }

function Test-SubtitleTrackKeptByOverride {
    param([string] $Language, [bool] $IsForced, [string] $Title, [string] $Codec, $StreamIndex, $SubtitleOverride)
    return $true
}

function Get-SubtitleTrackTitleOverride {
    param([string] $Language, [bool] $IsForced, $SubtitleOverride)
    return ''
}

function Get-SubtitleOperationTimeoutSeconds {
    param([string] $ScriptVariableName, [int] $DefaultSeconds)
    return $DefaultSeconds
}

$script:LogRows = [System.Collections.Generic.List[object]]::new()
$script:ConversionCalls = [System.Collections.Generic.List[string]]::new()
$script:SubtitleSwitches = @{
    DropAssAfterConversion = $false
    DropTx3gAfterConversion = $false
    DropBdpgsAfterConversion = $false
    DropVobSubAfterConversion = $false
}
$script:OutputContainer = 'mp4'
$script:PreferredSubtitleLanguage = 'eng'
$script:CanPreserveTx3g = $false
$script:CanPreserveBdpgs = $false
$script:CanPreserveVobSub = $false
$script:AssConversionMode = 'success'
$script:Tx3gConversionMode = 'success'
$script:BdpgsConversionMode = 'success'
$script:VobSubConversionMode = 'success'
$script:SubSDHTitleKeywords = @('sdh', 'hearing')
$script:SubSupplementalKeywords = @('sign', 'song', 'karaoke')
$script:SubtitleLanguagePolicy = @('eng')
$script:processingDir = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-subtitle-builder-decisions-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $script:processingDir -Force | Out-Null

try {
    . (Join-Path $repoRoot 'ops\pipeline\engine\shared\media_constants.ps1')
    . (Join-Path $repoRoot 'ops\pipeline\engine\subtitles\routing_decisions.ps1')
    . (Join-Path $repoRoot 'ops\pipeline\engine\subtitles\filtering.ps1')
    . (Join-Path $repoRoot 'ops\pipeline\engine\subtitles\builders.ps1')

    function Get-MkvmergeTidMap {
        param([string] $FilePath, [string] $Context)
        return $script:MkvmergeTidMap
    }

    # mkvmerge emits selected source tracks in source-TID order even when the
    # builder discovers converted/preserved tracks before a kept source track.
    # The verification plan must use the actual mux order, then append external
    # generated subtitle inputs in their argument order.
    $script:MkvmergeTidMap = @{ 3 = 3; 4 = 4; 5 = 5 }
    $script:ConversionCalls.Clear()
    $mkvOrderFilter = @{
        Convert = @(
            (New-TestSubtitleEntry -Index 4 -Lang 'eng' -Title 'English' -Codec 'ass'),
            (New-TestSubtitleEntry -Index 5 -Lang 'eng' -Title 'English CC' -Codec 'ass')
        )
        Tx3gConvert = @()
        BdpgsConvert = @()
        VobSubConvert = @()
        Keep = @(
            (New-TestSubtitleEntry -Index 3 -Lang 'eng' -Title 'English Signs' -Codec 'ass' -Forced -Supplemental)
        )
    }
    $mkvOrderBuild = Build-SubtitleTracksForMkvmerge -FilterResult $mkvOrderFilter -DefaultAudioLang 'jpn' -SourceFile (Join-Path $script:processingDir 'source.mkv') -Context 'TEST: '
    Assert-Equal ((@($mkvOrderBuild.SourceTracks) | ForEach-Object { $_.MkvTid }) -join ',') '3,4,5' 'mkvmerge source tracks must be returned in the order they appear in output.'
    Assert-Equal ((@($mkvOrderBuild.VerificationTracks) | ForEach-Object { $_.source_stream_index }) -join ',') '3,4,5,4,5' 'mkvmerge verification tracks must mirror source-TID output order before generated SRT inputs.'
    Assert-Equal ((@($mkvOrderBuild.VerificationTracks) | ForEach-Object { if ($_.is_forced) { '1' } else { '0' } }) -join ',') '1,0,0,0,0' 'mkvmerge verification order must keep the forced source track aligned to output ordinal zero.'
    @($mkvOrderBuild.TempFiles) | ForEach-Object { Remove-Item -LiteralPath $_ -Force -ErrorAction SilentlyContinue }
    $script:ConversionCalls.Clear()

    $probeFilter = Filter-SubtitleStreams -FilePath (Join-Path $script:processingDir 'source.mkv') -Context 'TEST: '
    Assert-True ($script:SubtitleProbeArgumentList -contains 'stream=index,codec_name,codec_long_name,codec_tag_string,codec_tag:stream_tags=language,title:stream_disposition=default,forced') 'Subtitle discovery must explicitly request ffprobe default/forced dispositions.'
    Assert-Equal @($probeFilter.Keep).Count 1 'Forced English SRT fixture should remain in the keep plan.'
    Assert-True ([bool]$probeFilter.Keep[0].IsForced) 'Subtitle discovery must carry the source forced disposition into the resolved plan.'

    $literalKeywordResults = & {
        . (Join-Path $repoRoot 'ops\pipeline\engine\subtitles\language_policy.ps1')
        [pscustomobject]@{
            QuestionMarkMatchesPlainTitle = Test-SubtitleTitleMatchesAnyKeyword -TitleLower 'regular dialogue' -Keywords @('?')
            BracketMatchesPlainTitle = Test-SubtitleTitleMatchesAnyKeyword -TitleLower 'regular dialogue' -Keywords @('[abc]')
            SongMatchesSongTitle = Test-SubtitleTitleMatchesAnyKeyword -TitleLower 'signs and songs' -Keywords @('song')
        }
    }
    Assert-True (-not [bool]$literalKeywordResults.QuestionMarkMatchesPlainTitle) 'Supplemental keyword matching should treat ? as a literal character, not a wildcard.'
    Assert-True (-not [bool]$literalKeywordResults.BracketMatchesPlainTitle) 'Supplemental keyword matching should treat bracket patterns as literal text.'
    Assert-True ([bool]$literalKeywordResults.SongMatchesSongTitle) 'Supplemental keyword matching should still match ordinary literal substrings.'

    $preferredAssRoutingDecision = Resolve-SubtitleRoutingDecision -Entry (New-TestSubtitleEntry -Index 8 -Lang 'eng' -Title 'English Preferred ASS' -Codec 'ass')
    Assert-Equal $preferredAssRoutingDecision.Action 'ConvertAss' 'Preferred-language ASS should remain conversion-eligible.'

    $nonPolicyForcedAssPolicy = Resolve-SubtitleStreamPolicy -SubtitleOrdinal 0 -Stream ([pscustomobject]@{
        index = 9
        codec_name = 'ass'
        codec_tag_string = ''
        tags = [pscustomobject]@{ language = 'jpn'; title = 'Japanese Forced ASS' }
        disposition = [pscustomobject]@{ forced = 1; default = 0 }
    })
    Assert-True (-not [bool]$nonPolicyForcedAssPolicy.Retain) 'Non-policy forced ASS should be dropped before routing.'
    Assert-True (-not [bool]$nonPolicyForcedAssPolicy.LanguagePolicyMatched) 'Non-policy forced ASS should not be marked conversion-language matched.'
    Assert-Equal $nonPolicyForcedAssPolicy.RetainReason 'language_or_title_policy' 'Non-policy forced ASS should not use forced metadata to bypass ASS language policy.'
    $nonPolicyForcedAssEntry = New-SubtitleFilterEntry -Policy $nonPolicyForcedAssPolicy
    Assert-True (-not [bool]$nonPolicyForcedAssEntry.LanguagePolicyMatched) 'Filter entry should carry non-policy ASS conversion evidence.'
    Assert-Equal $nonPolicyForcedAssEntry.RetainReason 'language_or_title_policy' 'Filter entry should carry non-policy ASS drop reason.'
    $nonPolicyForcedAssRoutingDecision = Resolve-SubtitleRoutingDecision -Entry $nonPolicyForcedAssEntry
    Assert-Equal $nonPolicyForcedAssRoutingDecision.Action 'Drop' 'Non-policy forced ASS should not be preserved or converted if it reaches routing.'
    Assert-ContainsText $nonPolicyForcedAssRoutingDecision.Message 'outside configured subtitle language policy' 'Non-policy forced ASS routing should explain why it was dropped.'

    $script:SubtitleLanguagePolicy = @('und')
    $blankAssPolicy = Resolve-SubtitleStreamPolicy -SubtitleOrdinal 1 -Stream ([pscustomobject]@{
        index = 18
        codec_name = 'ass'
        codec_tag_string = ''
        tags = [pscustomobject]@{ language = ''; title = 'Undefined ASS' }
        disposition = [pscustomobject]@{ forced = 0; default = 0 }
    })
    Assert-True ([bool]$blankAssPolicy.Retain) 'Blank-language ASS should be retained when policy includes und.'
    Assert-Equal $blankAssPolicy.Lang 'und' 'Blank-language ASS should normalize to und for filtering.'
    Assert-True ([bool]$blankAssPolicy.LanguagePolicyMatched) 'Blank-language ASS should match und language policy.'
    $blankAssDecision = Resolve-SubtitleRoutingDecision -Entry (New-SubtitleFilterEntry -Policy $blankAssPolicy)
    Assert-Equal $blankAssDecision.Action 'ConvertAss' 'Blank-language ASS should remain conversion-eligible when und is kept.'
    $script:SubtitleLanguagePolicy = @('eng')

    $script:SubtitleSwitches['ConvertBdpgsToSrt'] = $true
    $nonPolicyMetadataCases = @(
        @{ Kind = 'TX3G'; Index = 15; Codec = 'mov_text'; Language = 'jpn'; Title = 'Japanese Forced TX3G'; Forced = 1 },
        @{ Kind = 'BDPGS'; Index = 16; Codec = 'hdmv_pgs_subtitle'; Language = 'ger'; Title = 'German SDH'; Forced = 1 },
        @{ Kind = 'VobSub'; Index = 17; Codec = 'dvd_subtitle'; Language = 'ita'; Title = 'Italian SDH'; Forced = 1 }
    )
    foreach ($case in $nonPolicyMetadataCases) {
        $policy = Resolve-SubtitleStreamPolicy -SubtitleOrdinal ([int]$case.Index) -Stream ([pscustomobject]@{
            index = [int]$case.Index
            codec_name = [string]$case.Codec
            codec_tag_string = ''
            tags = [pscustomobject]@{ language = [string]$case.Language; title = [string]$case.Title }
            disposition = [pscustomobject]@{ forced = [int]$case.Forced; default = 0 }
        })
        Assert-True (-not [bool]$policy.Retain) "Non-policy $($case.Kind) SDH/forced metadata should not bypass configured subtitle languages."
        Assert-True (-not [bool]$policy.LanguagePolicyMatched) "Non-policy $($case.Kind) should not be marked language-policy matched."
        Assert-Equal $policy.RetainReason 'language_or_title_policy' "Non-policy $($case.Kind) drop should keep language-policy evidence."
        $decision = Resolve-SubtitleRoutingDecision -Entry (New-SubtitleFilterEntry -Policy $policy)
        Assert-Equal $decision.Action 'Drop' "Non-policy $($case.Kind) should not be converted or kept if it reaches routing."
        Assert-ContainsText $decision.Message 'outside configured subtitle language policy' "Non-policy $($case.Kind) routing should explain the language-policy drop."
    }

    $policyMatchedBdpgsPolicy = Resolve-SubtitleStreamPolicy -SubtitleOrdinal 3 -Stream ([pscustomobject]@{
        index = 16
        codec_name = 'hdmv_pgs_subtitle'
        codec_tag_string = ''
        tags = [pscustomobject]@{ language = 'eng'; title = 'English SDH' }
        disposition = [pscustomobject]@{ forced = 0; default = 0 }
    })
    Assert-True ([bool]$policyMatchedBdpgsPolicy.Retain) 'Policy-matched BDPGS should remain eligible for OCR.'
    Assert-True ([bool]$policyMatchedBdpgsPolicy.LanguagePolicyMatched) 'Policy-matched BDPGS should carry OCR language-policy evidence.'
    $policyMatchedBdpgsDecision = Resolve-SubtitleRoutingDecision -Entry (New-SubtitleFilterEntry -Policy $policyMatchedBdpgsPolicy)
    Assert-Equal $policyMatchedBdpgsDecision.Action 'ConvertBdpgs' 'Policy-matched BDPGS should remain conversion-eligible.'
    [void]$script:SubtitleSwitches.Remove('ConvertBdpgsToSrt')

    $filter = @{
        Convert = @(
            (New-TestSubtitleEntry -Index 10 -Lang 'eng' -Title 'English ASS' -Codec 'ass')
        )
        Tx3gConvert = @(
            (New-TestSubtitleEntry -Index 11 -Lang 'jpn' -Title 'Japanese TX3G' -Codec 'mov_text' -Tx3g)
        )
        BdpgsConvert = @(
            (New-TestSubtitleEntry -Index 12 -Lang 'eng' -Title 'English PGS' -Codec 'hdmv_pgs_subtitle' -Bdpgs)
        )
        Keep = @(
            (New-TestSubtitleEntry -Index 13 -Lang 'eng' -Title 'Kept PGS' -Codec 'hdmv_pgs_subtitle' -Bdpgs),
            (New-TestSubtitleEntry -Index 14 -Lang 'und' -Title 'Undefined SRT' -Codec 'subrip')
        )
    }

    $records = @(Get-SubtitleBuilderTrackDecisionRecords -FilterResult $filter -Builder 'FFmpeg' -CanPreserveTx3g:$false -CanPreserveBdpgs:$false)
    Assert-Equal $records.Count 5 'decision planner should emit one record per routed subtitle entry.'
    Assert-Equal $script:ConversionCalls.Count 0 'decision planner must not call conversion/OCR helpers.'
    Assert-Equal @(Get-ChildItem -LiteralPath $script:processingDir -Filter '*.srt' -File -ErrorAction SilentlyContinue).Count 0 'decision planner must not create SRT temp artifacts.'

    $assDecision = @($records | Where-Object { $_.Action -eq 'ConvertAss' })[0]
    Assert-True (-not $assDecision.PreserveOriginal) 'MP4 compatibility should not preserve embedded ASS after SRT conversion.'
    Assert-Equal $assDecision.ConversionKind 'ass_to_srt' 'ASS conversion decision should name the SRT conversion kind.'
    Assert-True $assDecision.ConversionFailureRoutesToReview 'ASS conversion failure should remain review-routed.'
    Assert-True $assDecision.IsPreferredDefaultCandidate 'English ASS should be a preferred default candidate.'

    $tx3gDecision = @($records | Where-Object { $_.Action -eq 'ConvertTx3g' })[0]
    Assert-True (-not $tx3gDecision.PreserveOriginal) 'TX3G should not be preserved when the FFmpeg output container cannot carry it.'
    Assert-Equal $tx3gDecision.OriginalPreserveReason 'container_does_not_preserve_tx3g' 'TX3G preserve reason should record container incompatibility.'
    Assert-ContainsText $tx3gDecision.ContainerLogMessage 'cannot be preserved as tx3g' 'TX3G decision should retain the operator-facing container warning.'

    $bdpgsConvertDecision = @($records | Where-Object { $_.Action -eq 'ConvertBdpgs' })[0]
    Assert-True (-not $bdpgsConvertDecision.PreserveOriginal) 'BDPGS should not be preserved when the FFmpeg output container cannot carry it.'
    Assert-Equal $bdpgsConvertDecision.OriginalPreserveReason 'container_does_not_preserve_bdpgs' 'BDPGS preserve reason should record container incompatibility.'
    Assert-True $bdpgsConvertDecision.ConversionFailureRoutesToReview 'BDPGS OCR failure should remain review-routed.'

    $bdpgsKeepDecision = @($records | Where-Object { $_.Action -eq 'Keep' -and $_.Entry.IsBdpgs })[0]
    Assert-True $bdpgsKeepDecision.RoutesToReview 'Kept BDPGS should route to review when FFmpeg output cannot preserve it.'
    Assert-Equal $bdpgsKeepDecision.ReviewErrorCode 'SUBTITLE_BDPGS_CONTAINER_UNSUPPORTED' 'Kept BDPGS review route should keep the existing error code.'

    $srtKeepDecision = @($records | Where-Object { $_.Action -eq 'Keep' -and $_.Entry.Stream.index -eq 14 })[0]
    Assert-True $srtKeepDecision.IsFallbackDefaultCandidate 'Undefined kept SRT should remain a fallback default candidate.'
    Assert-True $srtKeepDecision.RoutesToReview 'MP4 compatibility should route embedded SRT preserve attempts to review.'
    Assert-Equal $srtKeepDecision.ReviewErrorCode 'SUBTITLE_MP4_EXTERNAL_SRT_REQUIRED' 'MP4 embedded subtitle review route should be explicit.'

    $mp4Build = Build-SubtitleArgsForFFmpeg -FilterResult $filter -DefaultAudioLang 'eng' -SourceFile (Join-Path $script:processingDir 'source.mkv') -Context 'TEST: '
    Assert-Equal $mp4Build.TrackCount 0 'MP4 compatibility should not emit embedded subtitle tracks.'
    Assert-Equal $mp4Build.MapArgs.Count 0 'MP4 compatibility should not emit subtitle map args.'
    Assert-Equal $mp4Build.ExtraInputs.Count 0 'MP4 compatibility should not add generated SRT inputs for embedding.'
    Assert-Equal $mp4Build.Tx3gTracks.Count 1 'MP4 compatibility should reduce converted SRT sidecar candidates to exactly one publish record.'
    Assert-Equal $mp4Build.ConvertedSrtSidecarTracks.Count 1 'MP4 compatibility should expose the selected converted SRT sidecar through a source-neutral field.'
    Assert-Equal $mp4Build.ConvertedSrtSidecarCandidates.Count 3 'MP4 compatibility should retain durable evidence for every converted SRT candidate.'
    Assert-Equal $mp4Build.SubtitleOutputReduction.Count 2 'MP4 compatibility should retain durable evidence for every non-selected converted SRT candidate.'
    $selectedMp4Sidecar = @($mp4Build.ConvertedSrtSidecarTracks)[0]
    Assert-True $selectedMp4Sidecar.ContainsKey('ConversionKind') 'Selected MP4 sidecar should retain the conversion kind.'
    Assert-Equal $selectedMp4Sidecar.ConversionKind 'ass_to_srt' 'Selected MP4 sidecar should retain ASS-to-SRT provenance.'
    Assert-Equal $selectedMp4Sidecar.SourceSubtitleKind 'ass' 'Selected MP4 sidecar should retain the source subtitle kind.'
    Assert-Equal $selectedMp4Sidecar.SourceSubtitleCodec 'ass' 'Selected MP4 sidecar should retain the source subtitle codec.'
    Assert-Equal $selectedMp4Sidecar.SourceKind 'embedded' 'Selected MP4 sidecar should retain embedded-vs-sidecar provenance.'
    Assert-Equal @($mp4Build.Tx3gTracks)[0].ConversionKind 'ass_to_srt' 'Compatibility TX3G sidecar field should not erase non-TX3G provenance.'
    Assert-True ($mp4Build.DroppedEmbeddedTrackCount -ge 3) 'MP4 compatibility should report dropped embedded subtitle candidates.'
    $reducedMp4Kinds = (@($mp4Build.SubtitleOutputReduction) | ForEach-Object { $_.source_subtitle_kind }) -join ','
    Assert-ContainsText $reducedMp4Kinds 'tx3g' 'MP4 reduction evidence should identify reduced TX3G candidates.'
    Assert-ContainsText $reducedMp4Kinds 'bdpgs' 'MP4 reduction evidence should identify reduced BDPGS candidates.'
    Assert-True (-not [bool](@($mp4Build.SubtitleOutputReduction)[0].selected)) 'Reduced MP4 candidates should be marked as not selected.'

    $script:ConversionCalls.Clear()
    $mp4HighValueReductionFilter = @{
        Convert = @(
            (New-TestSubtitleEntry -Index 50 -Lang 'eng' -Title 'Main English ASS' -Codec 'ass'),
            (New-TestSubtitleEntry -Index 51 -Lang 'eng' -Title 'Forced English ASS' -Codec 'ass' -Forced),
            (New-TestSubtitleEntry -Index 52 -Lang 'eng' -Title 'Signs English ASS' -Codec 'ass' -Supplemental)
        )
        Tx3gConvert = @()
        BdpgsConvert = @()
        VobSubConvert = @()
        Keep = @()
    }
    $mp4HighValueReductionBuild = Build-SubtitleArgsForFFmpeg -FilterResult $mp4HighValueReductionFilter -DefaultAudioLang 'eng' -SourceFile (Join-Path $script:processingDir 'source.mkv') -Context 'TEST: '
    Assert-Equal $mp4HighValueReductionBuild.ConvertedSrtSidecarCandidates.Count 3 'High-value MP4 reduction should still record every converted candidate.'
    Assert-Equal $mp4HighValueReductionBuild.SubtitleOutputReduction.Count 2 'High-value MP4 reduction should record every non-selected candidate.'
    Assert-Equal @($mp4HighValueReductionBuild.Failures | Where-Object { $_.error_code -eq 'SUBTITLE_MP4_CONVERTED_SRT_REDUCTION_BLOCKED' }).Count 2 'Forced or supplemental MP4 reduction should fail closed before publish.'
    Assert-True ([bool](@($mp4HighValueReductionBuild.SubtitleOutputReduction) | Where-Object { $_.is_forced })) 'MP4 reduction evidence should identify reduced forced candidates.'
    Assert-True ([bool](@($mp4HighValueReductionBuild.SubtitleOutputReduction) | Where-Object { $_.is_supplemental })) 'MP4 reduction evidence should identify reduced supplemental candidates.'

    $script:ConversionCalls.Clear()
    $mp4SourceDefaultAssFilter = @{
        Convert = @(
            (New-TestSubtitleEntry -Index 40 -Lang 'jpn' -Title 'Japanese Source Default ASS' -Codec 'ass' -SourceDefault),
            (New-TestSubtitleEntry -Index 41 -Lang 'eng' -Title 'English Preferred ASS' -Codec 'ass')
        )
        Tx3gConvert = @()
        BdpgsConvert = @()
        VobSubConvert = @()
        Keep = @()
    }
    $mp4SourceDefaultAssBuild = Build-SubtitleArgsForFFmpeg -FilterResult $mp4SourceDefaultAssFilter -DefaultAudioLang 'jpn' -SourceFile (Join-Path $script:processingDir 'source.mkv') -Context 'TEST: '
    Assert-Equal ($script:ConversionCalls -join ',') 'ass:40,ass:41' 'MP4 compatibility should still evaluate converted ASS candidates in routed order.'
    Assert-Equal $mp4SourceDefaultAssBuild.ConvertedSrtSidecarTracks.Count 1 'MP4 compatibility should still select exactly one converted ASS sidecar.'
    $selectedAssSidecar = @($mp4SourceDefaultAssBuild.ConvertedSrtSidecarTracks)[0]
    Assert-Equal $selectedAssSidecar.StreamInfo.Lang 'eng' 'MP4 compatibility should prefer the converted preferred-language ASS SRT over a source-default non-English ASS.'
    Assert-True ([bool]$selectedAssSidecar.StreamInfo.IsDefault) 'Selected converted ASS SRT should carry the converted default disposition evidence.'

    $mkvRecords = @(Get-SubtitleBuilderTrackDecisionRecords -FilterResult $filter -Builder 'Mkvmerge')
    $mkvAssDecision = @($mkvRecords | Where-Object { $_.Action -eq 'ConvertAss' })[0]
    Assert-True $mkvAssDecision.PreserveOriginal 'mkvmerge ASS conversion should preserve the original ASS subtitle when drop-original is disabled.'
    Assert-Equal $mkvAssDecision.OriginalPreserveReason 'preserved' 'mkvmerge ASS preserve reason should remain preserved.'
    $mkvBdpgsDecision = @($mkvRecords | Where-Object { $_.Action -eq 'ConvertBdpgs' })[0]
    Assert-True $mkvBdpgsDecision.PreserveOriginal 'mkvmerge BDPGS conversion should preserve the original image subtitle when drop-original is disabled.'
    Assert-Equal $mkvBdpgsDecision.OriginalPreserveReason 'preserved' 'mkvmerge BDPGS preserve reason should remain preserved.'

    $vobSubFilter = @{
        Convert = @()
        Tx3gConvert = @()
        BdpgsConvert = @()
        VobSubConvert = @(
            (New-TestSubtitleEntry -Index 15 -Lang 'eng' -Title 'English VobSub' -Codec 'dvd_subtitle' -VobSub)
        )
        Keep = @(
            (New-TestSubtitleEntry -Index 16 -Lang 'eng' -Title 'Kept VobSub' -Codec 'dvd_subtitle' -VobSub)
        )
    }
    $vobSubRecords = @(Get-SubtitleBuilderTrackDecisionRecords -FilterResult $vobSubFilter -Builder 'FFmpeg' -CanPreserveVobSub:$false)
    $vobSubConvertDecision = @($vobSubRecords | Where-Object { $_.Action -eq 'ConvertVobSub' })[0]
    Assert-True (-not $vobSubConvertDecision.PreserveOriginal) 'VobSub should not be preserved when the FFmpeg output container cannot carry it.'
    Assert-Equal $vobSubConvertDecision.OriginalPreserveReason 'container_does_not_preserve_vobsub' 'VobSub preserve reason should record container incompatibility.'
    Assert-Equal $vobSubConvertDecision.ConversionKind 'vobsub_to_srt' 'VobSub conversion decision should name the SRT conversion kind.'
    Assert-True $vobSubConvertDecision.ConversionFailureRoutesToReview 'VobSub OCR failure should remain review-routed.'
    $vobSubKeepDecision = @($vobSubRecords | Where-Object { $_.Action -eq 'Keep' -and $_.Entry.IsVobSub })[0]
    Assert-True $vobSubKeepDecision.RoutesToReview 'Kept VobSub should route to review when FFmpeg output cannot preserve it.'
    Assert-Equal $vobSubKeepDecision.ReviewErrorCode 'SUBTITLE_VOBSUB_CONTAINER_UNSUPPORTED' 'Kept VobSub review route should use the VobSub error code.'

    $mkvVobSubRecords = @(Get-SubtitleBuilderTrackDecisionRecords -FilterResult $vobSubFilter -Builder 'Mkvmerge')
    $mkvVobSubDecision = @($mkvVobSubRecords | Where-Object { $_.Action -eq 'ConvertVobSub' })[0]
    Assert-True $mkvVobSubDecision.PreserveOriginal 'mkvmerge VobSub conversion should preserve the original image subtitle when drop-original is disabled.'
    Assert-Equal $mkvVobSubDecision.OriginalPreserveReason 'preserved' 'mkvmerge VobSub preserve reason should remain preserved.'

    $vobSubSidecarFilter = @{
        Convert = @()
        Tx3gConvert = @()
        BdpgsConvert = @()
        VobSubConvert = @(
            (New-TestSubtitleEntry -Index -1 -Lang 'eng' -Title 'English VobSub sidecar' -Codec 'vobsub' -VobSub -SourceKind 'sidecar')
        )
        Keep = @()
    }
    $vobSubSidecarDecision = @(Get-SubtitleBuilderTrackDecisionRecords -FilterResult $vobSubSidecarFilter -Builder 'Mkvmerge' | Where-Object { $_.Action -eq 'ConvertVobSub' })[0]
    Assert-True (-not $vobSubSidecarDecision.PreserveOriginal) 'External VobSub sidecars should not be muxed as original tracks.'
    Assert-Equal $vobSubSidecarDecision.OriginalPreserveReason 'external_sidecar_preserved_outside_output' 'External VobSub sidecar preserve reason should not imply source deletion.'

    $vobSubSidecarKeepFilter = @{
        Convert = @()
        Tx3gConvert = @()
        BdpgsConvert = @()
        VobSubConvert = @()
        Keep = @(
            (New-TestSubtitleEntry -Index -1 -Lang 'eng' -Title 'Kept VobSub sidecar' -Codec 'vobsub' -VobSub -SourceKind 'sidecar')
        )
    }
    $vobSubSidecarKeepDecision = @(Get-SubtitleBuilderTrackDecisionRecords -FilterResult $vobSubSidecarKeepFilter -Builder 'Mkvmerge' | Where-Object { $_.Action -eq 'Keep' })[0]
    Assert-True $vobSubSidecarKeepDecision.RoutesToReview 'External VobSub sidecars kept without OCR should route to review instead of silent publish.'
    Assert-Equal $vobSubSidecarKeepDecision.ReviewErrorCode 'SUBTITLE_VOBSUB_SIDECAR_PRESERVE_UNSUPPORTED' 'External VobSub sidecar preserve review should use the sidecar-specific error code.'

    $script:OutputContainer = 'mkv'
    $script:ConversionCalls.Clear()
    $build = Build-SubtitleArgsForFFmpeg -FilterResult $filter -DefaultAudioLang 'jpn' -SourceFile (Join-Path $script:processingDir 'source.mkv') -Context 'TEST: '
    Assert-Equal $build.TrackCount 5 'FFmpeg builder should emit preserved ASS, converted ASS/TX3G/BDPGS, and kept SRT tracks while excluding review-routed kept BDPGS.'
    Assert-Equal $build.ExtraInputs.Count 6 'FFmpeg builder should keep SRT input argument ordering for three generated SRT files.'
    Assert-Equal $build.TempFiles.Count 3 'FFmpeg builder should track only successfully generated temp SRT artifacts.'
    Assert-Equal @($build.Failures | Where-Object { $_.error_code -eq 'SUBTITLE_BDPGS_CONTAINER_UNSUPPORTED' }).Count 1 'Unsupported kept BDPGS should still produce a review failure record.'
    Assert-Equal ($script:ConversionCalls -join ',') 'ass:10,tx3g:11,bdpgs:12' 'FFmpeg builder should call conversion/OCR helpers in original group order.'
    Assert-Equal $build.ExtraInputs[0] '-i' 'First generated subtitle input should start with -i.'
    Assert-Equal (Split-Path -Leaf $build.ExtraInputs[1]) 'ass_10.srt' 'First generated subtitle input should be the ASS SRT.'
    Assert-Equal $build.ExtraInputs[2] '-i' 'Second generated subtitle input should start with -i.'
    Assert-True ((Split-Path -Leaf $build.ExtraInputs[3]) -like 'sub_tx3g_*.srt') 'Second generated subtitle input should be the TX3G SRT temp artifact.'
    Assert-Equal $build.ExtraInputs[4] '-i' 'Third generated subtitle input should start with -i.'
    Assert-True ((Split-Path -Leaf $build.ExtraInputs[5]) -like 'sub_bdpgs_*.srt') 'Third generated subtitle input should be the BDPGS SRT temp artifact.'

    $expectedMapArgs = @(
        '-map', '0:10',
        '-c:s:0', 'copy',
        '-metadata:s:s:0', 'title=English ASS [ASS]',
        '-metadata:s:s:0', 'language=eng',
        '-disposition:s:0', 'default',
        '-map', '1:s:0',
        '-c:s:1', 'srt',
        '-metadata:s:s:1', 'title=English ASS',
        '-metadata:s:s:1', 'language=eng',
        '-disposition:s:1', '0',
        '-map', '2:s:0',
        '-c:s:2', 'srt',
        '-metadata:s:s:2', 'title=Japanese TX3G',
        '-metadata:s:s:2', 'language=jpn',
        '-disposition:s:2', '0',
        '-map', '3:s:0',
        '-c:s:3', 'srt',
        '-metadata:s:s:3', 'title=English PGS',
        '-metadata:s:s:3', 'language=eng',
        '-disposition:s:3', '0',
        '-map', '0:14',
        '-c:s:4', 'copy',
        '-metadata:s:s:4', 'title=Undefined SRT',
        '-metadata:s:s:4', 'language=und',
        '-disposition:s:4', '0'
    )
    Assert-Equal ($build.MapArgs -join "`n") ($expectedMapArgs -join "`n") 'FFmpeg subtitle map/codec/metadata/disposition args should remain in the expected output-stream order.'

    $disp0 = [array]::IndexOf($build.MapArgs, '-disposition:s:0')
    $disp1 = [array]::IndexOf($build.MapArgs, '-disposition:s:1')
    $disp2 = [array]::IndexOf($build.MapArgs, '-disposition:s:2')
    Assert-Equal $build.MapArgs[$disp0 + 1] 'default' 'Preserved ASS should receive default disposition when ASS styling is preserved.'
    Assert-Equal $build.MapArgs[$disp1 + 1] '0' 'Converted preferred-language ASS SRT should remain an embedded fallback option.'
    Assert-Equal $build.MapArgs[$disp2 + 1] '0' 'Later converted TX3G should not take default after preferred ASS succeeds.'

    # MKV can stream-copy the generated SRT input, but ffprobe still reports
    # the resulting codec as subrip. Verification must model the media codec,
    # not the literal FFmpeg encoder argument.
    $script:ConvertedSrtCodec = 'copy'
    $script:ConversionCalls.Clear()
    $copyCodecBuild = Build-SubtitleArgsForFFmpeg -FilterResult $filter -DefaultAudioLang 'jpn' -SourceFile (Join-Path $script:processingDir 'source.mkv') -Context 'TEST COPY: '
    $copyCodecConvertedTracks = @($copyCodecBuild.VerificationTracks | Where-Object { $_.action -in @('convert_ass', 'convert_tx3g', 'convert_bdpgs') })
    Assert-Equal ($copyCodecConvertedTracks.output_codec -join ',') 'subrip,subrip,subrip' 'Stream-copied generated SRT tracks must verify as subrip output codecs.'
    $script:ConvertedSrtCodec = 'srt'

    $script:ConversionCalls.Clear()
    $script:AssConversionMode = 'fail'
    $failureFilter = @{
        Convert = @(
            (New-TestSubtitleEntry -Index 20 -Lang 'eng' -Title 'English ASS' -Codec 'ass')
        )
        Tx3gConvert = @()
        BdpgsConvert = @()
        Keep = @(
            (New-TestSubtitleEntry -Index 21 -Lang 'eng' -Title 'Later English SRT' -Codec 'subrip')
        )
    }
    $failureBuild = Build-SubtitleArgsForFFmpeg -FilterResult $failureFilter -DefaultAudioLang 'jpn' -SourceFile (Join-Path $script:processingDir 'source.mkv') -Context 'TEST: '
    Assert-Equal @($failureBuild.Failures | Where-Object { $_.error_code -eq 'SUBTITLE_ASS_CONVERT_FAILED' }).Count 1 'ASS conversion failure should still surface as a review-routed failure record.'
    Assert-Equal $failureBuild.TrackCount 2 'Failed ASS conversion should keep the preserved ASS track and continue to later kept tracks.'
    $failDisp0 = [array]::IndexOf($failureBuild.MapArgs, '-disposition:s:0')
    $failDisp1 = [array]::IndexOf($failureBuild.MapArgs, '-disposition:s:1')
    Assert-Equal $failureBuild.MapArgs[$failDisp0 + 1] 'default' 'Preserved ASS should receive default when preferred SRT conversion fails.'
    Assert-Equal $failureBuild.MapArgs[$failDisp1 + 1] '0' 'Later English SRT should not steal default after preserved failed-conversion ASS receives it.'

    $script:AssConversionMode = 'success'
    $script:Tx3gConversionMode = 'fail'
    $script:BdpgsConversionMode = 'fail'
    $script:VobSubConversionMode = 'fail'
    $script:ConversionCalls.Clear()
    $failedOcrFilter = @{
        Convert = @()
        Tx3gConvert = @(
            (New-TestSubtitleEntry -Index 30 -Lang 'eng' -Title 'Bad TX3G' -Codec 'mov_text' -Tx3g)
        )
        BdpgsConvert = @(
            (New-TestSubtitleEntry -Index 31 -Lang 'eng' -Title 'Bad PGS' -Codec 'hdmv_pgs_subtitle' -Bdpgs)
        )
        VobSubConvert = @(
            (New-TestSubtitleEntry -Index 32 -Lang 'eng' -Title 'Bad VobSub' -Codec 'dvd_subtitle' -VobSub)
        )
        Keep = @()
    }
    $failedOcrBuild = Build-SubtitleArgsForFFmpeg -FilterResult $failedOcrFilter -DefaultAudioLang 'jpn' -SourceFile (Join-Path $script:processingDir 'source.mkv') -Context 'TEST: '
    Assert-Equal ($script:ConversionCalls -join ',') 'tx3g:30,bdpgs:31,vobsub:32' 'Failed bitmap/text conversions should still run in original group order.'
    Assert-Equal $failedOcrBuild.TrackCount 0 'Failed TX3G/BDPGS/VobSub conversion without preservable originals should not emit subtitle tracks as silent success.'
    Assert-Equal $failedOcrBuild.TempFiles.Count 0 'Failed TX3G/BDPGS/VobSub conversion should not register temp SRT artifacts.'
    Assert-Equal @($failedOcrBuild.Failures | Where-Object { $_.error_code -eq 'SUBTITLE_TX3G_EXTRACT_FAILED' }).Count 1 'TX3G conversion failure should remain review-routed.'
    Assert-Equal @($failedOcrBuild.Failures | Where-Object { $_.error_code -eq 'SUBTITLE_BDPGS_OCR_FAILED' }).Count 1 'BDPGS OCR failure should remain review-routed.'
    Assert-Equal @($failedOcrBuild.Failures | Where-Object { $_.error_code -eq 'SUBTITLE_VOBSUB_OCR_FAILED' }).Count 1 'VobSub OCR failure should remain review-routed.'
    $script:Tx3gConversionMode = 'success'
    $script:BdpgsConversionMode = 'success'
    $script:VobSubConversionMode = 'success'

    $script:ConversionCalls.Clear()
    $textBurnEntry = New-TestSubtitleEntry -Index 33 -Lang 'eng' -Title 'English SRT burn' -Codec 'subrip'
    $textBurnEntry['SubtitleInputOrdinal'] = 1
    $textBurnBuild = Build-SubtitleArgsForFFmpeg -FilterResult @{ Burn = @($textBurnEntry) } -DefaultAudioLang 'jpn' -SourceFile (Join-Path $script:processingDir 'source.mkv') -Context 'TEST: '
    Assert-Equal $textBurnBuild.TrackCount 0 'Text subtitle burn should not emit selectable subtitle output tracks.'
    Assert-Equal $textBurnBuild.MapArgs.Count 0 'Text subtitle burn should not map selectable subtitles.'
    Assert-Equal $textBurnBuild.ExtraInputs.Count 0 'Text subtitle burn should not create generated subtitle inputs.'
    Assert-Equal $script:ConversionCalls.Count 0 'Text subtitle burn should render directly instead of using OCR/conversion helpers.'
    Assert-ContainsText ($textBurnBuild.VideoFilterArgs -join ' ') '-filter_complex' 'Text subtitle burn should emit a video filter graph.'
    Assert-ContainsText ($textBurnBuild.VideoFilterArgs -join ' ') 'subtitles=filename=' 'Text subtitle burn should use the FFmpeg subtitles filter.'
    Assert-ContainsText ($textBurnBuild.VideoFilterArgs -join ' ') ':si=1' 'Text subtitle burn should select the exact subtitle input ordinal.'
    Assert-Equal $textBurnBuild.VideoFilterArgs[-2] '-map' 'Text subtitle burn should map the filtered video output.'
    Assert-Equal $textBurnBuild.VideoFilterArgs[-1] '[vout]' 'Text subtitle burn should map only the burn-filtered video pad.'

    $imageBurnEntry = New-TestSubtitleEntry -Index 34 -Lang 'eng' -Title 'English PGS burn' -Codec 'hdmv_pgs_subtitle' -Bdpgs
    $imageBurnEntry['SubtitleInputOrdinal'] = 2
    $imageBurnBuild = Build-SubtitleArgsForFFmpeg -FilterResult @{ Burn = @($imageBurnEntry) } -DefaultAudioLang 'jpn' -SourceFile (Join-Path $script:processingDir 'source.mkv') -Context 'TEST: '
    Assert-Equal $imageBurnBuild.TrackCount 0 'Image subtitle burn should not emit selectable subtitle output tracks.'
    Assert-Equal $imageBurnBuild.MapArgs.Count 0 'Image subtitle burn should not map selectable subtitles.'
    Assert-Equal $imageBurnBuild.ExtraInputs.Count 0 'Image subtitle burn should not create generated subtitle inputs.'
    Assert-ContainsText ($imageBurnBuild.VideoFilterArgs -join ' ') 'overlay=eof_action=pass:repeatlast=0' 'Image subtitle burn should overlay the exact bitmap subtitle ordinal.'
    Assert-Equal ([int]$imageBurnBuild.BurnTrack.Stream.index) 34 'Image subtitle burn should keep evidence for the burned stream index.'

    . (Join-Path $repoRoot 'ops\pipeline\engine\subtitles\srt.ps1')
    $validSrtPath = Join-Path $script:processingDir 'valid.srt'
    Write-TestSrt -Path $validSrtPath -Text 'valid'
    Assert-True ([bool](Test-SrtFileUsable -Path $validSrtPath).Ok) 'SRT validation should accept a cue with timing and text.'

    $emptyCueSrtPath = Join-Path $script:processingDir 'empty-cue.srt'
    [System.IO.File]::WriteAllText($emptyCueSrtPath, "1`r`n00:00:00,000 --> 00:00:01,000`r`n", [System.Text.UTF8Encoding]::new($false))
    Assert-True (-not [bool](Test-SrtFileUsable -Path $emptyCueSrtPath).Ok) 'SRT validation should reject timing-only cues with no text.'

    $strayTextSrtPath = Join-Path $script:processingDir 'stray-text.srt'
    [System.IO.File]::WriteAllText($strayTextSrtPath, "stray text`r`n1`r`n00:00:00,000 --> 00:00:01,000`r`nvalid`r`n", [System.Text.UTF8Encoding]::new($false))
    Assert-True (-not [bool](Test-SrtFileUsable -Path $strayTextSrtPath).Ok) 'SRT validation should reject text outside cue timing blocks.'

    $reversedTimingSrtPath = Join-Path $script:processingDir 'reversed-timing.srt'
    [System.IO.File]::WriteAllText($reversedTimingSrtPath, "1`r`n00:00:02,000 --> 00:00:01,000`r`ninvalid`r`n", [System.Text.UTF8Encoding]::new($false))
    Assert-True (-not [bool](Test-SrtFileUsable -Path $reversedTimingSrtPath).Ok) 'SRT validation should reject cues whose end time is not after the start time.'

    $mergeSrtPath = Join-Path $script:processingDir 'merge-adjacent.srt'
    [System.IO.File]::WriteAllText($mergeSrtPath, "1`r`n00:00:00,000 --> 00:00:01,000`r`nHello`r`n`r`n2`r`n00:00:01,050 --> 00:00:02,000`r`nHello`r`n", [System.Text.UTF8Encoding]::new($false))
    Merge-AdjacentIdenticalCues -SrtPath $mergeSrtPath -ThresholdMs 150
    $mergedSrtText = [System.IO.File]::ReadAllText($mergeSrtPath, [System.Text.Encoding]::UTF8)
    Assert-ContainsText $mergedSrtText '00:00:00,000 --> 00:00:02,000' 'SRT adjacent identical cue merge should use the local timestamp parser and extend the first cue.'
    Assert-True ([bool](Test-SrtFileUsable -Path $mergeSrtPath).Ok) 'Merged SRT should remain usable after atomic rewrite.'

    . (Join-Path $repoRoot 'ops\pipeline\engine\subtitles\bdpgs.ps1')
    $bdpgsPipeGlyphText = "1`r`n00:00:00,200 --> 00:00:01,400`r`n| never said |t was over.`r`n`r`n2`r`n00:00:01,500 --> 00:00:02,000`r`nNo pipe here.`r`n"
    $bdpgsPipeGlyphRepair = Repair-BdpgsOcrSrtPipeGlyphText -Text $bdpgsPipeGlyphText
    Assert-Equal $bdpgsPipeGlyphRepair.ReplacementCount 2 'BDPGS OCR pipe-glyph repair should count only cue text replacements.'
    Assert-ContainsText $bdpgsPipeGlyphRepair.Text 'I never said It was over.' 'BDPGS OCR pipe-glyph repair should replace pipe glyphs in cue text with uppercase I.'
    Assert-ContainsText $bdpgsPipeGlyphRepair.Text '00:00:00,200 --> 00:00:01,400' 'BDPGS OCR pipe-glyph repair should preserve timing lines.'

    $bdpgsPipeGlyphPath = Join-Path $script:processingDir 'bdpgs-pipe-glyph.srt'
    [System.IO.File]::WriteAllText($bdpgsPipeGlyphPath, $bdpgsPipeGlyphText, [System.Text.UTF8Encoding]::new($false))
    $bdpgsPipeGlyphFileRepair = Repair-BdpgsOcrSrtPipeGlyphs -Path $bdpgsPipeGlyphPath -Context 'TEST: '
    $bdpgsPipeGlyphFileText = [System.IO.File]::ReadAllText($bdpgsPipeGlyphPath, [System.Text.Encoding]::UTF8)
    Assert-Equal $bdpgsPipeGlyphFileRepair.ReplacementCount 2 'BDPGS OCR pipe-glyph file repair should report rewritten cue text replacements.'
    Assert-ContainsText $bdpgsPipeGlyphFileText 'I never said It was over.' 'BDPGS OCR pipe-glyph file repair should persist uppercase I replacements.'
    Assert-True (-not ($bdpgsPipeGlyphFileText -match '\|')) 'BDPGS OCR pipe-glyph file repair should remove OCR pipe glyphs from cue text.'

    function Get-NormalizedSubtitleLanguage {
        param([string] $Language)
        if ([string]::IsNullOrWhiteSpace($Language)) { return 'und' }
        return $Language
    }

    function Get-SubtitleOperationTimeoutSeconds {
        param([string] $ScriptVariableName, [int] $DefaultSeconds)
        return $DefaultSeconds
    }

    function Extract-BdpgsToSup {
        param(
            [Parameter(Mandatory)] [string]$SourceFile,
            [Parameter(Mandatory)] [int]$StreamIndex,
            [Parameter(Mandatory)] [string]$DestinationPath,
            [hashtable]$StreamInfo = @{},
            [string]$Context = ""
        )
        [System.IO.File]::WriteAllText($DestinationPath, 'fake sup payload', [System.Text.UTF8Encoding]::new($false))
        return [pscustomobject]@{ Ok = $true; Path = $DestinationPath; Reason = 'ok'; Failure = $null }
    }

    function Invoke-BdpgsOcrCommand {
        param(
            [string] $FilePath,
            [array] $ArgumentList,
            [int] $TimeoutSeconds,
            [string] $Stage,
            [switch] $SaveReproOnFailure,
            [string] $ProcessPriority
        )
        $script:BdpgsOcrInvocationCount++
        $outputIndex = [array]::IndexOf($ArgumentList, '--output')
        $outputPath = [string]$ArgumentList[$outputIndex + 1]
        [System.IO.File]::WriteAllText($outputPath, "1`r`n00:00:00,200 --> 00:00:01,400`r`n| am here.`r`n", [System.Text.UTF8Encoding]::new($false))
        return [pscustomobject]@{ ExitCode = 0; Error = ''; ReproPath = $null }
    }

    $script:BdpgsOcrToolPath = $PSCommandPath
    $script:BdpgsOcrTessdataPath = ''
    $script:BdpgsOcrInvocationCount = 0
    Assert-Equal (Resolve-BdpgsOcrLanguage 'und') 'und' 'BDPGS OCR must not silently default undetermined language to English.'
    Assert-Equal (Resolve-BdpgsOcrLanguage '') 'und' 'BDPGS OCR must not silently default blank language to English.'
    $bdpgsConvertedPath = Join-Path $script:processingDir 'bdpgs-converted-pipe-glyph.srt'
    $bdpgsConverted = Convert-BdpgsToSrt -SourceFile (Join-Path $script:processingDir 'source.mkv') -StreamIndex 40 -StreamInfo (New-TestSubtitleEntry -Index 40 -Lang 'eng' -Title 'English PGS' -Codec 'hdmv_pgs_subtitle' -Bdpgs) -DestinationPath $bdpgsConvertedPath -Context 'TEST: '
    Assert-True ([bool]$bdpgsConverted.Ok) ("BDPGS OCR conversion with pipe-glyph repair should succeed: {0}" -f $bdpgsConverted.Reason)
    $bdpgsConvertedText = [System.IO.File]::ReadAllText($bdpgsConvertedPath, [System.Text.Encoding]::UTF8)
    Assert-ContainsText $bdpgsConvertedText 'I am here.' 'BDPGS OCR conversion should repair pipe glyphs before accepting the SRT.'
    Assert-True (-not ($bdpgsConvertedText -match '\|')) 'BDPGS OCR conversion should not publish OCR pipe glyphs in cue text.'

    $script:BdpgsOcrInvocationCount = 0
    $bdpgsUnknownLanguagePath = Join-Path $script:processingDir 'bdpgs-unknown-language.srt'
    $bdpgsUnknownLanguage = Convert-BdpgsToSrt -SourceFile (Join-Path $script:processingDir 'source.mkv') -StreamIndex 41 -StreamInfo (New-TestSubtitleEntry -Index 41 -Lang 'und' -Title 'Unknown PGS' -Codec 'hdmv_pgs_subtitle' -Bdpgs) -DestinationPath $bdpgsUnknownLanguagePath -Context 'TEST: '
    Assert-True (-not [bool]$bdpgsUnknownLanguage.Ok) 'BDPGS conversion should fail before OCR when the OCR language is unknown.'
    Assert-Equal $bdpgsUnknownLanguage.Failure.ErrorCode 'SUBTITLE_BDPGS_OCR_LANGUAGE_UNKNOWN' 'Unknown BDPGS OCR language should use a distinct failure code.'
    Assert-Equal $script:BdpgsOcrInvocationCount 0 'Unknown BDPGS OCR language should not invoke the OCR tool.'
} finally {
    Remove-Item -LiteralPath $script:processingDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'Subtitle builder decision checks passed.'
