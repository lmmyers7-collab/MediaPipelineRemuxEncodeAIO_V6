[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Remux split stage checks require PowerShell 7. Install pwsh or use the bundled runtime."
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

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-False {
    param([bool] $Condition, [string] $Message)
    if ($Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Assert-OrderContainsBefore {
    param([string] $First, [string] $Second, [string] $Message)
    $firstIndex = [array]::IndexOf([object[]]$script:RemuxGateOrder.ToArray(), $First)
    $secondIndex = [array]::IndexOf([object[]]$script:RemuxGateOrder.ToArray(), $Second)
    Assert-True ($firstIndex -ge 0) "$Message Missing '$First'."
    Assert-True ($secondIndex -ge 0) "$Message Missing '$Second'."
    Assert-True ($firstIndex -lt $secondIndex) $Message
}

function Assert-ContainsSubsequence {
    param([array] $Haystack, [array] $Needles, [string] $Message)
    $position = 0
    foreach ($needle in @($Needles)) {
        $found = $false
        while ($position -lt $Haystack.Count) {
            if ([string]$Haystack[$position] -eq [string]$needle) {
                $found = $true
                $position++
                break
            }
            $position++
        }
        if (-not $found) {
            throw "$Message Missing subsequence token '$needle'. Actual: $($Haystack -join ' ')"
        }
    }
}

$remuxModulePaths = @(
    'ops\pipeline\engine\process\remux_context.ps1',
    'ops\pipeline\engine\process\remux_preflight.ps1',
    'ops\pipeline\engine\process\remux_subtitle_plan.ps1',
    'ops\pipeline\engine\process\remux_ffmpeg_av_stage.ps1',
    'ops\pipeline\engine\process\remux_mkvmerge_args.ps1',
    'ops\pipeline\engine\process\remux_mkvmerge_stage.ps1',
    'ops\pipeline\engine\process\remux_verification.ps1',
    'ops\pipeline\engine\process\remux_publish.ps1',
    'ops\pipeline\engine\process\remux_orchestrator.ps1',
    'ops\pipeline\entrypoints\MediaPipeline\remux.ps1'
)
foreach ($relativePath in $remuxModulePaths) {
    . (Join-Path $repoRoot $relativePath)
}

$script:RemuxHarnessRoots = [System.Collections.Generic.List[string]]::new()

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
}

function DebugLog {
    param([string] $Message)
}

function Set-ProgressStage {
    param([string] $Stage, [string] $Status, [string] $Route, [string] $CopyState, $Percent, [switch] $SaveNow)
}

function Get-SafeLocalName {
    param([string] $Name)
    return $Name
}

function Ensure-ScratchCopy {
    param($File, [string] $SafeName)
    return $script:ScratchPath
}

function Get-OutputPaths {
    param($File, [bool] $IsTV, $TvInfo, [string] $SafeName)
    return $script:CurrentPaths
}

function Test-OutputNeedsReprocess {
    param([string] $OutputPath, $SourceFile)
    return $false
}

function Invoke-Tx3gSidecarExportForExistingOutput {
    param($SourceFile, [string] $ScratchPath, [string] $MediaOutputPath, [string] $Context)
    return $true
}

function New-ExistingOutputPublishResult {
    param($SourceFile, [string] $OutputPath)
    return [pscustomobject][ordered]@{
        Ok                = $true
        DeleteLocalOutput = $false
        KeepScratchInput  = $false
        OutputPath        = $OutputPath
    }
}

function Clear-SourceFailureState {
    param($SourceFile)
}

function Test-DiskSpace {
    param([string] $Path, [double] $MinGB, [string] $Label)
    return $true
}

function Test-EstimatedOutputSpace {
    param([string] $SourcePath, [string] $Label, [switch] $RemuxTwoStage, [switch] $RemuxFinalStage)
    return $true
}

function Get-SourceVideoCodec {
    param([string] $FilePath)
    return 'h264'
}

function Resolve-RemuxCodecRoutePlan {
    param([string] $SourceCodec, [string[]] $RemuxSafeVideoCodecs, $BasePlan)
    return [pscustomobject][ordered]@{
        Route              = $script:NextCodecRoute
        ReasonCode         = $script:NextCodecReasonCode
        Reason             = $script:NextCodecReason
        DecisionTrace      = @()
        SourceCodec        = $SourceCodec
        SourceMediaProfile = [pscustomobject][ordered]@{ is_hdr = $false }
    }
}

function New-MediaRouteDecisionTraceEntry {
    param([string] $Code, [string] $Message, $Data)
    return [pscustomobject][ordered]@{
        code    = $Code
        message = $Message
        data    = $Data
    }
}

function Test-SourceVideoStreamPublishPolicy {
    param([string] $FilePath, [string] $Route)
    return [pscustomobject][ordered]@{
        Allowed   = $true
        Reason    = ''
        ErrorCode = ''
        Inventory = [pscustomobject][ordered]@{ video_stream_count = 1 }
    }
}

function Get-HDRState {
    param([string] $FilePath)
    return [pscustomobject][ordered]@{ Known = $true; IsHDR = $false; Reason = '' }
}

function Get-DolbyVisionState {
    param([string] $FilePath)
    return [pscustomobject][ordered]@{ Present = $false }
}

function Test-Hdr10PlusPresence {
    param([string] $FilePath)
    return [pscustomobject][ordered]@{ Present = $false }
}

function New-DynamicHdrEvidence {
    param([string] $Route, $DoviState, $Hdr10PlusState)
    return [pscustomobject][ordered]@{
        dynamic_metadata_present = $false
        summary                  = 'none'
    }
}

function Build-AudioArgs {
    param([string] $InputPath)
    $script:LastAudioTrackCount = 1
    $script:LastAudioDefaultIndex = 0
    $script:LastAudioTranscodeActive = $false
    return @('-map', '0:a:0', '-c:a:0', 'copy')
}

function Get-DefaultAudioLang {
    param([string] $InputPath)
    return 'eng'
}

function Filter-SubtitleStreams {
    param([string] $InputPath, [string] $Context, [string] $OriginalSourcePath)
    return [pscustomobject][ordered]@{
        ProbeFailed = $false
        Reason      = ''
        ErrorCode   = ''
    }
}

function Get-MediaVideoCodecHevcNames {
    return @('hevc', 'h265')
}

function Acquire-CpuEncodeMutex {
    param([int] $TimeoutSeconds)
    return [pscustomobject][ordered]@{
        Acquired = $true
        Reason   = ''
        Release  = { }
    }
}

function Invoke-FFmpegWithProgress {
    param(
        [array] $FFArgs,
        [string] $Label,
        [string] $InputFile,
        [int] $TimeoutSeconds,
        [string] $ProgressStage,
        [string] $ProgressRoute,
        [string] $ReproStage,
        [switch] $CpuEncode,
        [string] $ProcessPriority
    )
    $script:RemuxGateOrder.Add('ffmpeg') | Out-Null
    $script:LastFfmpegArgs = @($FFArgs)
    $tempAvPath = [string]$FFArgs[-1]
    Set-Content -LiteralPath $tempAvPath -Value 'temp-av' -NoNewline
    return $true
}

function Get-ErrorTextSummary {
    param([string] $ErrorText)
    return ''
}

function Get-FFmpegFailureCode {
    param([string] $Stage, [string] $ErrorText, [int] $ExitCode)
    return 'FFMPEG_FAILED'
}

function Build-SubtitleTracksForMkvmerge {
    param($SubFilter, [string] $DefaultAudioLang, [string] $InputPath, [string] $Context)
    $script:RemuxGateOrder.Add('subtitle-ready') | Out-Null
    if ($script:IncludeSubtitleTracks) {
        $externalSrt = Join-Path $script:RemuxCurrentRoot 'external.eng.srt'
        Set-Content -LiteralPath $externalSrt -Value "1`n00:00:00,000 --> 00:00:01,000`nhello" -NoNewline
        return [pscustomobject][ordered]@{
            Failures                       = @()
            SourceTracks                   = @([pscustomobject][ordered]@{
                MkvTid    = 2
                Lang      = 'jpn'
                Title     = 'Japanese'
                IsDefault = $false
                IsForced  = $true
            })
            ExternalTracks                 = @([pscustomobject][ordered]@{
                SrtPath   = $externalSrt
                Lang      = 'eng'
                Title     = 'English SRT'
                IsDefault = $true
                IsForced  = $false
            })
            Tx3gTracks                     = @([pscustomobject][ordered]@{ index = 3 })
            BdpgsTracks                    = @([pscustomobject][ordered]@{ index = 4 })
            VobSubTracks                   = @([pscustomobject][ordered]@{ index = 5 })
            ConvertedSrtSidecarCandidates  = @($externalSrt)
            SubtitleOutputReduction        = [pscustomobject][ordered]@{ reduced = $false }
            TempFiles                      = @()
        }
    }
    return [pscustomobject][ordered]@{
        Failures                       = @()
        SourceTracks                   = @()
        ExternalTracks                 = @()
        Tx3gTracks                     = @()
        BdpgsTracks                    = @()
        VobSubTracks                   = @()
        ConvertedSrtSidecarCandidates  = @()
        SubtitleOutputReduction        = $null
        TempFiles                      = @()
    }
}

function Register-SubtitleExtractionFailure {
    param($SourceFile, [string] $ScratchPath, [array] $Failures, [string] $Stage)
    $script:RegisteredFailures.Add($Stage) | Out-Null
}

function Get-SourceTitleTag {
    param([string] $FilePath)
    return ''
}

function Get-MkvmergeAudioTids {
    param([string] $FilePath, [string] $Context)
    return @(1)
}

function Invoke-MkvmergeWithProgress {
    param(
        [array] $ArgumentList,
        [string] $Label,
        [int] $TimeoutSeconds,
        [string] $Stage,
        [string] $ProgressStage,
        [string] $ProgressRoute,
        [switch] $SaveReproOnFailure
    )
    $script:RemuxGateOrder.Add('mkvmerge') | Out-Null
    $script:LastMkvArgs = @($ArgumentList)
    $outputIndex = [array]::IndexOf([object[]]$ArgumentList, '--output')
    if ($script:MkvmergeCreatesOutput -and $outputIndex -ge 0 -and $outputIndex + 1 -lt $ArgumentList.Count) {
        Set-Content -LiteralPath ([string]$ArgumentList[$outputIndex + 1]) -Value 'mkv-output' -NoNewline
    }
    return [pscustomobject][ordered]@{
        ExitCode                  = $script:MkvmergeExitCode
        TimedOut                  = $false
        Stopped                   = $false
        MkvmergeWarningBlocking   = $false
        ToolErrorCode             = ''
        MkvmergeWarningMatchedText = ''
        ReproPath                 = 'mkvmerge.repro.ps1'
        Error                     = ''
        Output                    = ''
    }
}

function Get-MkvmergeFailureCode {
    param([string] $ErrorText, [int] $ExitCode, [bool] $TimedOut, [bool] $Stopped)
    if ($TimedOut) { return 'MKVMERGE_TIMEOUT' }
    if ($Stopped) { return 'MKVMERGE_STOPPED' }
    return 'MKVMERGE_FAILED'
}

function Test-DurationMatch {
    param([string] $SourcePath, [string] $OutputPath, [string] $Label, [switch] $AllowAVFallback)
    $script:RemuxGateOrder.Add('duration') | Out-Null
    return $script:DurationOk
}

function Test-OutputVideoStreamPreservation {
    param([string] $SourcePath, [string] $OutputPath, [string] $Route, $SourceInventory)
    $script:RemuxGateOrder.Add('video-preservation') | Out-Null
    return [pscustomobject][ordered]@{
        Allowed     = $script:VideoPreservationOk
        Reason      = if ($script:VideoPreservationOk) { '' } else { 'video stream missing' }
        ErrorCode   = if ($script:VideoPreservationOk) { '' } else { 'VIDEO_STREAM_MISSING' }
        SourceCount = 1
        OutputCount = if ($script:VideoPreservationOk) { 1 } else { 0 }
    }
}

function Write-PlexCompatibilityReport {
    param([string] $FilePath, [string] $Context)
}

function Complete-PipelineOutputPublish {
    param(
        $SourceFile,
        [string] $ScratchPath,
        $Paths,
        [string] $Route,
        [string] $ProgressRoute,
        [string] $StagePrefix,
        [string] $Context,
        [string] $RouteReasonCode,
        [string] $RouteReason,
        [array] $Tx3gTracks,
        [array] $BdpgsTracks,
        [array] $VobSubTracks,
        [array] $ConvertedSrtSidecarCandidates,
        $SubtitleOutputReduction
    )
    Assert-Equal $Route 'remux' 'Remux publish route drifted.'
    Assert-Equal $ProgressRoute 'remux' 'Remux publish progress route drifted.'
    Assert-Equal $StagePrefix 'remux' 'Remux publish stage prefix drifted.'
    Assert-Equal $Context 'REMUX: ' 'Remux publish context drifted.'
    Assert-True (Test-Path -LiteralPath $Paths.LocalOut -PathType Leaf) 'Publish must not run before final remux output exists.'
    $script:RemuxGateOrder.Add('publish') | Out-Null
    Assert-OrderContainsBefore 'mkvmerge' 'publish' 'Publish must run after accepted mkvmerge execution.'
    Assert-OrderContainsBefore 'subtitle-ready' 'publish' 'Publish must run after subtitle/sidecar state is ready.'
    Assert-OrderContainsBefore 'duration' 'publish' 'Publish must run after duration verification.'
    Assert-OrderContainsBefore 'video-preservation' 'publish' 'Publish must run after video-stream preservation verification.'
    return [pscustomobject][ordered]@{
        Ok                = $script:PublishOk
        DeleteLocalOutput = $script:PublishDeleteLocalOutput
        KeepScratchInput  = $script:PublishKeepScratchInput
    }
}

function Register-SourceFailure {
    param(
        $SourceFile,
        [string] $ScratchPath,
        [string] $Classification,
        [string] $Reason,
        [string] $Stage,
        [string] $ErrorCode,
        [string] $ReproPath,
        [string] $SuggestedAction,
        $AdditionalProperties
    )
    $script:RegisteredFailures.Add($Stage) | Out-Null
}

function Remove-ScratchFingerprint {
    param([string] $ScratchPath)
}

function Remove-EmptyScratchContainer {
    param([string] $ScratchPath)
}

function Do-Encode {
    param($file, [bool] $isTV, $tvInfo)
    $script:DoEncodeCalled = $true
    return $script:DoEncodeReturn
}

function Reset-RemuxHarness {
    param(
        [string] $CodecRoute = 'remux',
        [bool] $KeepScratchInput = $false,
        [bool] $DeleteLocalOutput = $false,
        [bool] $DurationPasses = $true,
        [bool] $VideoPreservationPasses = $true,
        [int] $MkvmergeExitCode = 0,
        [bool] $MkvmergeCreatesOutput = $true,
        [bool] $IncludeSubtitleTracks = $false
    )

    $root = Join-Path ([System.IO.Path]::GetTempPath()) "mediapipeline-remux-split-$([guid]::NewGuid().ToString('N'))"
    [System.IO.Directory]::CreateDirectory($root) | Out-Null
    $script:RemuxCurrentRoot = $root
    $script:RemuxHarnessRoots.Add($root) | Out-Null

    $sourcePath = Join-Path $root 'source.mkv'
    $script:ScratchPath = Join-Path $root 'scratch.mkv'
    $localDir = Join-Path $root 'local'
    $serverDir = Join-Path $root 'server'
    [System.IO.Directory]::CreateDirectory($localDir) | Out-Null
    [System.IO.Directory]::CreateDirectory($serverDir) | Out-Null
    Set-Content -LiteralPath $sourcePath -Value 'source' -NoNewline
    Set-Content -LiteralPath $script:ScratchPath -Value 'scratch' -NoNewline

    $script:SourceFile = Get-Item -LiteralPath $sourcePath
    $script:CurrentPaths = [pscustomobject][ordered]@{
        LocalDir  = $localDir
        ServerDir = $serverDir
        LocalOut  = Join-Path $localDir 'output.mkv'
        ServerOut = Join-Path $serverDir 'output.mkv'
    }
    $script:RemuxGateOrder = [System.Collections.Generic.List[string]]::new()
    $script:RegisteredFailures = [System.Collections.Generic.List[string]]::new()
    $script:NextCodecRoute = $CodecRoute
    $script:NextCodecReasonCode = if ($CodecRoute -eq 'remux') { 'codec_remux_safe' } else { 'codec_forces_encode' }
    $script:NextCodecReason = if ($CodecRoute -eq 'remux') { 'codec can remux' } else { 'codec must encode' }
    $script:CurrentRoutePlan = [pscustomobject][ordered]@{
        SourceCodec        = 'h264'
        SourceMediaProfile = [pscustomobject][ordered]@{ is_hdr = $false }
    }
    $script:CurrentRouteReasonCode = 'initial_route'
    $script:CurrentRouteReason = 'initial route reason'
    $script:CurrentSizePolicyResult = [pscustomobject][ordered]@{ message = 'encoded output is oversized' }
    $script:LastRemuxFallbackRejection = [pscustomobject][ordered]@{ stale = $true }
    $script:LastDynamicHdrRemuxFallbackRejection = [pscustomobject][ordered]@{ stale = $true }
    $script:LastPublishResult = $null
    $script:LastFFmpegReproPath = ''
    $script:LastFFmpegStderr = ''
    $script:LastFFmpegExit = 0
    $script:LastFFmpegErrorLog = ''
    $script:LastAudioTrackCount = 1
    $script:LastAudioDefaultIndex = 0
    $script:LastAudioTranscodeActive = $false
    $script:CpuEncodeMaxThreads = 0
    $script:CpuEncodeProcessPriority = 'BelowNormal'
    $script:FFmpegRemuxTimeoutSeconds = 10
    $script:MkvmergeRemuxTimeoutSeconds = 10
    $script:pipelineStatus = 'Processing'
    $script:ProductVersion = 'test-product'
    $script:PipelineVersion = 'test-pipeline'
    $script:processingDir = $root
    $script:LocalFailed = $root
    $script:LocalBase = $root
    $script:MinFreeSpaceGB = 0
    $script:RemuxSafeVideoCodecs = @('h264', 'hevc')
    $script:PublishOk = $true
    $script:PublishKeepScratchInput = $KeepScratchInput
    $script:PublishDeleteLocalOutput = $DeleteLocalOutput
    $script:DurationOk = $DurationPasses
    $script:VideoPreservationOk = $VideoPreservationPasses
    $script:MkvmergeExitCode = $MkvmergeExitCode
    $script:MkvmergeCreatesOutput = $MkvmergeCreatesOutput
    $script:IncludeSubtitleTracks = $IncludeSubtitleTracks
    $script:LastFfmpegArgs = @()
    $script:LastMkvArgs = @()
    $script:DoEncodeCalled = $false
    $script:DoEncodeReturn = $true
}

try {
    Reset-RemuxHarness -KeepScratchInput $true -DeleteLocalOutput $true
    $ok = Do-Remux $script:SourceFile $false $null
    Assert-True $ok 'Successful remux should return true.'
    Assert-True ($null -ne $script:LastPublishResult) 'Successful remux should set LastPublishResult.'
    Assert-OrderContainsBefore 'ffmpeg' 'mkvmerge' 'mkvmerge must run after the FFmpeg AV stage.'
    Assert-OrderContainsBefore 'mkvmerge' 'duration' 'Duration verification must run after accepted mkvmerge.'
    Assert-OrderContainsBefore 'duration' 'video-preservation' 'Video preservation verification must run after duration verification.'
    Assert-OrderContainsBefore 'video-preservation' 'publish' 'Publish must run after video preservation verification.'
    Assert-ContainsSubsequence $script:LastFfmpegArgs @('-fflags', '+genpts', '-i', $script:ScratchPath, '-map', '0:V', '-c:v', 'copy') 'REMUX-AV command shape drifted before video stream-copy mapping.'
    Assert-ContainsSubsequence $script:LastFfmpegArgs @('-map', '0:t?', '-map_chapters', '0', '-map_metadata', '0') 'REMUX-AV command shape drifted for attachments, chapters, or metadata.'
    Assert-ContainsSubsequence $script:LastMkvArgs @('--output', $script:CurrentPaths.LocalOut, '--title') 'REMUX-MUX command shape drifted before output/title arguments.'
    Assert-ContainsSubsequence $script:LastMkvArgs @('--default-track', '1:yes') 'REMUX-MUX command shape must include explicit audio default-track flags.'
    Assert-True (Test-Path -LiteralPath $script:ScratchPath -PathType Leaf) 'KeepScratchInput publish result should preserve scratch input.'
    Assert-False (Test-Path -LiteralPath $script:CurrentPaths.LocalOut -PathType Leaf) 'DeleteLocalOutput publish result should delete local output after successful push.'

    Reset-RemuxHarness -IncludeSubtitleTracks:$true
    $ok = Do-Remux $script:SourceFile $false $null
    Assert-True $ok 'Subtitle-bearing remux harness should return true.'
    Assert-ContainsSubsequence $script:LastMkvArgs @('--language', '2:jpn', '--track-name', '2:Japanese', '--default-track', '2:no', '--forced-track', '2:yes') 'REMUX-MUX command shape drifted for source subtitle track flags.'
    Assert-ContainsSubsequence $script:LastMkvArgs @('--no-video', '--no-audio', '--subtitle-tracks', '2', $script:ScratchPath) 'REMUX-MUX command shape drifted for source subtitle input mapping.'
    $externalSrt = Join-Path $script:RemuxCurrentRoot 'external.eng.srt'
    Assert-ContainsSubsequence $script:LastMkvArgs @('--language', '0:eng', '--track-name', '0:English SRT', '--default-track', '0:yes', $externalSrt) 'REMUX-MUX command shape drifted for external subtitle input mapping.'

    Reset-RemuxHarness -CodecRoute 'remux' -KeepScratchInput $true
    $ok = Do-Remux $script:SourceFile $false $null -FallbackFromOversizedEncode
    Assert-True $ok 'Accepted oversized encode remux fallback should return true.'
    Assert-True ($null -eq $script:LastRemuxFallbackRejection) 'Accepted oversized encode remux fallback should clear rejection evidence.'
    Assert-Equal $script:CurrentRouteReasonCode 'oversized_encode_remux_fallback' 'Accepted oversized encode remux fallback route reason code drifted.'
    Assert-True ([string]$script:CurrentRouteReason -like '*direct-copy size/bitrate caps bypassed*') 'Accepted oversized encode remux fallback must retain bypass warning evidence.'
    Assert-True ($null -ne $script:LastPublishResult) 'Accepted oversized encode remux fallback should set LastPublishResult.'
    Assert-True (Test-Path -LiteralPath $script:ScratchPath -PathType Leaf) 'Oversized encode remux fallback should preserve scratch input after return to encode context.'

    Reset-RemuxHarness -CodecRoute 'encode'
    $ok = Do-Remux $script:SourceFile $false $null -FallbackFromOversizedEncode
    Assert-False $ok 'Rejected oversized encode remux fallback should return false.'
    Assert-True ($null -ne $script:LastRemuxFallbackRejection) 'Rejected oversized encode remux fallback should record structured evidence.'
    Assert-Equal $script:LastRemuxFallbackRejection.reason_code 'codec_forces_encode' 'Rejected oversized encode remux fallback reason code drifted.'
    Assert-False ($script:RemuxGateOrder.ToArray() -contains 'publish') 'Rejected oversized encode remux fallback must not publish.'
    Assert-True (Test-Path -LiteralPath $script:ScratchPath -PathType Leaf) 'Rejected oversized encode remux fallback should preserve scratch input.'

    Reset-RemuxHarness -CodecRoute 'encode'
    $script:CurrentRouteReasonCode = 'dynamic_hdr_preserve_or_remux'
    $script:CurrentRouteReason = 'dynamic HDR preserve_or_remux fallback'
    $ok = Do-Remux $script:SourceFile $false $null -FallbackFromDynamicHdrEncode
    Assert-False $ok 'Rejected Dynamic HDR remux fallback should return false.'
    Assert-True ($null -ne $script:LastDynamicHdrRemuxFallbackRejection) 'Rejected Dynamic HDR remux fallback should record structured evidence.'
    Assert-Equal $script:LastDynamicHdrRemuxFallbackRejection.original_route_reason_code 'dynamic_hdr_preserve_or_remux' 'Dynamic HDR remux fallback original route reason code drifted.'
    Assert-False ($script:RemuxGateOrder.ToArray() -contains 'publish') 'Rejected Dynamic HDR remux fallback must not publish.'
    Assert-True (Test-Path -LiteralPath $script:ScratchPath -PathType Leaf) 'Rejected Dynamic HDR remux fallback should preserve scratch input.'

    Reset-RemuxHarness -DurationPasses:$false
    $ok = Do-Remux $script:SourceFile $false $null
    Assert-False $ok 'Duration verification failure should return false.'
    Assert-False ($script:RemuxGateOrder.ToArray() -contains 'publish') 'Duration verification failure must block publish.'
    Assert-True ($script:RegisteredFailures.ToArray() -contains 'remux-verify') 'Duration verification failure should register remux-verify evidence.'

    Reset-RemuxHarness -MkvmergeExitCode 2
    $ok = Do-Remux $script:SourceFile $false $null
    Assert-False $ok 'mkvmerge failure should return false.'
    Assert-False ($script:RemuxGateOrder.ToArray() -contains 'publish') 'mkvmerge failure must block publish.'
    Assert-True ($script:RegisteredFailures.ToArray() -contains 'remux-mkvmerge') 'mkvmerge failure should register remux-mkvmerge evidence.'

    Reset-RemuxHarness -MkvmergeCreatesOutput:$false
    $ok = Do-Remux $script:SourceFile $false $null
    Assert-False $ok 'Missing remux output should return false.'
    Assert-False ($script:RemuxGateOrder.ToArray() -contains 'publish') 'Missing remux output must block publish.'
    Assert-True ($script:RegisteredFailures.ToArray() -contains 'remux-mkvmerge') 'Missing remux output should register remux-mkvmerge evidence.'
} finally {
    foreach ($root in @($script:RemuxHarnessRoots.ToArray())) {
        if (-not [string]::IsNullOrWhiteSpace($root) -and $root.StartsWith([System.IO.Path]::GetTempPath(), [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host 'Remux split stage checks passed.'
