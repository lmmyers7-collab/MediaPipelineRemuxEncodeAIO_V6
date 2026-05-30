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

function Get-ConvertedSrtCodecForFfmpegOutput {
    return 'srt'
}

function Test-CanPreserveTx3gInFfmpegOutput {
    return [bool]$script:CanPreserveTx3g
}

function Test-CanPreserveBdpgsInFfmpegOutput {
    return [bool]$script:CanPreserveBdpgs
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

function New-TestSubtitleEntry {
    param(
        [int] $Index,
        [string] $Lang,
        [string] $Title,
        [string] $Codec = 'subrip',
        [switch] $Supplemental,
        [switch] $Forced,
        [switch] $Tx3g,
        [switch] $Bdpgs
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

$script:LogRows = [System.Collections.Generic.List[object]]::new()
$script:ConversionCalls = [System.Collections.Generic.List[string]]::new()
$script:SubtitleSwitches = @{
    DropAssAfterConversion = $false
    DropTx3gAfterConversion = $false
    DropBdpgsAfterConversion = $false
}
$script:OutputContainer = 'mp4'
$script:PreferredSubtitleLanguage = 'eng'
$script:CanPreserveTx3g = $false
$script:CanPreserveBdpgs = $false
$script:AssConversionMode = 'success'
$script:Tx3gConversionMode = 'success'
$script:BdpgsConversionMode = 'success'
$script:processingDir = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-subtitle-builder-decisions-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $script:processingDir -Force | Out-Null

try {
    . (Join-Path $repoRoot 'engine\subtitles\builders.ps1')

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
    Assert-True $assDecision.PreserveOriginal 'ASS conversion decision should preserve the source track when drop-original is disabled.'
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

    $mkvRecords = @(Get-SubtitleBuilderTrackDecisionRecords -FilterResult $filter -Builder 'Mkvmerge')
    $mkvBdpgsDecision = @($mkvRecords | Where-Object { $_.Action -eq 'ConvertBdpgs' })[0]
    Assert-True $mkvBdpgsDecision.PreserveOriginal 'mkvmerge BDPGS conversion should preserve the original image subtitle when drop-original is disabled.'
    Assert-Equal $mkvBdpgsDecision.OriginalPreserveReason 'preserved' 'mkvmerge BDPGS preserve reason should remain preserved.'

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
        '-disposition:s:0', '0',
        '-map', '1:s:0',
        '-c:s:1', 'srt',
        '-metadata:s:s:1', 'title=English ASS',
        '-metadata:s:s:1', 'language=eng',
        '-disposition:s:1', 'default',
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
    Assert-Equal $build.MapArgs[$disp0 + 1] '0' 'Preserved ASS should not take default when converted SRT succeeds.'
    Assert-Equal $build.MapArgs[$disp1 + 1] 'default' 'Converted preferred-language ASS SRT should receive default disposition after success.'
    Assert-Equal $build.MapArgs[$disp2 + 1] '0' 'Later converted TX3G should not take default after preferred ASS SRT succeeds.'

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
    $script:ConversionCalls.Clear()
    $failedOcrFilter = @{
        Convert = @()
        Tx3gConvert = @(
            (New-TestSubtitleEntry -Index 30 -Lang 'eng' -Title 'Bad TX3G' -Codec 'mov_text' -Tx3g)
        )
        BdpgsConvert = @(
            (New-TestSubtitleEntry -Index 31 -Lang 'eng' -Title 'Bad PGS' -Codec 'hdmv_pgs_subtitle' -Bdpgs)
        )
        Keep = @()
    }
    $failedOcrBuild = Build-SubtitleArgsForFFmpeg -FilterResult $failedOcrFilter -DefaultAudioLang 'jpn' -SourceFile (Join-Path $script:processingDir 'source.mkv') -Context 'TEST: '
    Assert-Equal ($script:ConversionCalls -join ',') 'tx3g:30,bdpgs:31' 'Failed TX3G/BDPGS conversions should still run in original group order.'
    Assert-Equal $failedOcrBuild.TrackCount 0 'Failed TX3G/BDPGS conversion without preservable originals should not emit subtitle tracks as silent success.'
    Assert-Equal $failedOcrBuild.TempFiles.Count 0 'Failed TX3G/BDPGS conversion should not register temp SRT artifacts.'
    Assert-Equal @($failedOcrBuild.Failures | Where-Object { $_.error_code -eq 'SUBTITLE_TX3G_EXTRACT_FAILED' }).Count 1 'TX3G conversion failure should remain review-routed.'
    Assert-Equal @($failedOcrBuild.Failures | Where-Object { $_.error_code -eq 'SUBTITLE_BDPGS_OCR_FAILED' }).Count 1 'BDPGS OCR failure should remain review-routed.'
} finally {
    Remove-Item -LiteralPath $script:processingDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'Subtitle builder decision checks passed.'
