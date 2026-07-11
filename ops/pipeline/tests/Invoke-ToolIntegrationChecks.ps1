[CmdletBinding()]
param(
    [switch]$AllowMissingTools
)

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent $testsRoot
$opsRoot = Split-Path -Parent $pipelineRoot
$projectRoot = Split-Path -Parent $opsRoot

$bundledPwshPath = Join-Path $pipelineRoot 'runtime\PowerShell-7.6.0-win-x64\pwsh.exe'
$ffmpegPath = Join-Path $pipelineRoot 'tools\ffmpeg\bin\ffmpeg.exe'
$ffprobePath = Join-Path $pipelineRoot 'tools\ffmpeg\bin\ffprobe.exe'
$pythonPath = Join-Path $projectRoot 'apps\desktop\runtime\Python\python.exe'
$assToSrtPath = Join-Path $projectRoot 'src\mediapipeline\pipeline\ass_to_srt_cli.py'

$missingTools = @()
foreach ($tool in @(
    @{ Name = 'PowerShell'; Path = $bundledPwshPath },
    @{ Name = 'ffmpeg';     Path = $ffmpegPath },
    @{ Name = 'ffprobe';    Path = $ffprobePath },
    @{ Name = 'Python';     Path = $pythonPath }
)) {
    if (-not (Test-Path -LiteralPath $tool.Path -PathType Leaf)) {
        $missingTools += "$($tool.Name) ($($tool.Path))"
    }
}

if ($missingTools.Count -gt 0) {
    $missingMessage = "Bundled tool integration checks require: {0}" -f ($missingTools -join ', ')
    if ($AllowMissingTools) {
        Write-Host "SKIP: $missingMessage"
        return
    }
    throw $missingMessage
}

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) { throw $Message }
}

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $script:IntegrationLog += ,([pscustomobject]@{ Message = $Message; Level = $Level })
}

function DebugLog {
    param([string]$Message)
    Write-Log -Message $Message -Level 'DEBUG'
}

function Set-ProgressStage {
    param(
        [string]$Stage,
        [string]$Status,
        [string]$Route,
        $Percent,
        [switch]$SaveNow
    )
    $script:IntegrationProgress += ,([pscustomobject]@{
        Stage = $Stage
        Status = $Status
        Route = $Route
        Percent = $Percent
        SaveNow = [bool]$SaveNow
    })
}

function Save-Progress {
    param($Status)
    $script:IntegrationSavedProgress += ,$Status
    return $true
}

function Write-PipelineEvent {
    param(
        [string]$EventType,
        [string]$Stage = '',
        [string]$SourcePath = '',
        [string]$Route = '',
        [string]$Status = '',
        [string]$JobId = '',
        [string]$CorrelationId = '',
        $Data = $null
    )
    $script:IntegrationEvents += ,([pscustomobject]@{
        EventType = $EventType
        Stage = $Stage
        SourcePath = $SourcePath
        Route = $Route
        Status = $Status
        JobId = $JobId
        CorrelationId = $CorrelationId
        Data = $Data
    })
    return $true
}

. (Join-Path $projectRoot 'ops\pipeline\engine\shared\path_helpers.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\shared\failure_codes.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\failures\failure_state.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\shared\native.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\probe\media_probe.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\verify\media_track_verification.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\process\ffmpeg_progress.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\subtitles\srt.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\subtitles\common.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\subtitles\tx3g.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\subtitles\bdpgs.ps1')

$workRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-tool-integration-" + [guid]::NewGuid().ToString("N"))
$StopFlag = Join-Path $workRoot 'stop.flag'
$PauseFlag = Join-Path $workRoot 'pause.flag'
$LocalFailed = Join-Path $workRoot 'Failed'
$LocalFailureReports = Join-Path $LocalFailed 'Reports'

$script:IntegrationLog = @()
$script:IntegrationEvents = @()
$script:IntegrationProgress = @()
$script:IntegrationSavedProgress = @()
$script:FFmpegProgressWriteStepPercent = 25
$script:pipelineStatus = 'IntegrationTest'
$script:StopRequested = $false
$script:SubtitleExtractTimeoutSeconds = 60
$script:BdpgsOcrTimeoutSeconds = 60
$script:AllowSystemTools = $false
$scriptDir = $pipelineRoot
$OutputContainer = 'mkv'
$Global:ffmpegProcess = $null
$previousPythonPath = $env:PYTHONPATH

try {
    $srcPath = Join-Path $projectRoot 'src'
    $env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($previousPythonPath)) { $srcPath } else { "$srcPath;$previousPythonPath" }
    New-Item -ItemType Directory -Path $workRoot, $LocalFailed, $LocalFailureReports -Force | Out-Null
    Assert-True (Test-Path -LiteralPath $assToSrtPath -PathType Leaf) "ASS helper is missing: $assToSrtPath"

    $sourcePath = Join-Path $workRoot 'source.mp4'
    $encodedPath = Join-Path $workRoot 'encoded.mkv'

    $generateResult = Invoke-FFmpegCommand -Stage 'integration-generate' -TimeoutSeconds 30 -ArgumentList @(
        '-hide_banner',
        '-loglevel', 'error',
        '-y',
        '-f', 'lavfi',
        '-i', 'testsrc=size=64x64:rate=5:duration=2',
        '-f', 'lavfi',
        '-i', 'sine=frequency=1000:sample_rate=44100:duration=2',
        '-shortest',
        '-c:v', 'mpeg4',
        '-q:v', '5',
        '-c:a', 'aac',
        '-movflags', '+faststart',
        $sourcePath
    )
    Assert-True ([int]$generateResult.ExitCode -eq 0) ("bundled ffmpeg failed to generate temp media: {0}" -f $generateResult.Error)
    Assert-True ((Test-Path -LiteralPath $sourcePath -PathType Leaf) -and ((Get-Item -LiteralPath $sourcePath).Length -gt 0)) 'temp media was not generated'
    Assert-True ([string]$generateResult.ToolErrorCode -eq 'OK') 'ffmpeg wrapper did not classify generation success as OK'

    $probeResult = Invoke-FFprobeCommand -Stage 'integration-probe-source' -TimeoutSeconds 30 -ArgumentList @(
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        '--',
        $sourcePath
    )
    Assert-True ([int]$probeResult.ExitCode -eq 0) ("bundled ffprobe failed to read generated media: {0}" -f $probeResult.Error)
    Assert-True ([string]$probeResult.ToolErrorCode -eq 'OK') 'ffprobe wrapper did not classify probe success as OK'

    $durationSeconds = [double]0
    $durationText = ([string]$probeResult.Output).Trim()
    $parsedDuration = [double]::TryParse(
        $durationText,
        [System.Globalization.NumberStyles]::Float,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [ref]$durationSeconds
    )
    Assert-True $parsedDuration ("ffprobe duration was not parseable: {0}" -f $durationText)
    Assert-True ($durationSeconds -ge 1.5 -and $durationSeconds -le 3.0) ("ffprobe duration was outside expected range: {0}" -f $durationSeconds)

    $progressOk = Invoke-FFmpegWithProgress `
        -FFArgs @(
            '-hide_banner',
            '-loglevel', 'error',
            '-y',
            '-i', $sourcePath,
            '-c:v', 'mpeg4',
            '-q:v', '5',
            '-c:a', 'aac',
            $encodedPath
        ) `
        -Label 'INTEGRATION-FFMPEG' `
        -InputFile $sourcePath `
        -TimeoutSeconds 30 `
        -ProgressStage 'integration-encode' `
        -ProgressRoute 'integration' `
        -ReproStage 'integration-encode'

    Assert-True $progressOk 'Invoke-FFmpegWithProgress returned false for bundled ffmpeg encode'
    Assert-True ((Test-Path -LiteralPath $encodedPath -PathType Leaf) -and ((Get-Item -LiteralPath $encodedPath).Length -gt 0)) 'progress encode did not create output media'
    Assert-True ([int]$script:LastFFmpegExit -eq 0) ("progress encode exit code changed: {0}" -f $script:LastFFmpegExit)
    Assert-True ([string]$script:LastFFmpegToolErrorCode -eq 'OK') ("progress encode error classification changed: {0}" -f $script:LastFFmpegToolErrorCode)
    Assert-True ([double]$script:LastFFmpegDurationSeconds -gt 0) 'progress encode did not record duration'
    Assert-True (-not $Global:ffmpegProcess) 'global ffmpeg process handle was not cleared'
    Assert-True ([string]$script:LastFFmpegCommandLine -match [regex]::Escape('-progress pipe:2 -nostats')) 'progress encode command line did not include ffmpeg progress arguments'

    $progressValues = @($script:IntegrationProgress | Where-Object { $_.Stage -eq 'integration-encode' } | ForEach-Object { $_.Percent })
    Assert-True ($progressValues -contains 0) 'progress encode did not publish initial 0 percent'
    Assert-True ($progressValues -contains 100) 'progress encode did not publish final 100 percent'

    $encodedProbe = Invoke-FFprobeCommand -Stage 'integration-probe-encoded' -TimeoutSeconds 30 -ArgumentList @(
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=codec_type',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        '--',
        $encodedPath
    )
    Assert-True ([int]$encodedProbe.ExitCode -eq 0) ("bundled ffprobe failed to read encoded output: {0}" -f $encodedProbe.Error)
    Assert-True (([string]$encodedProbe.Output).Trim() -eq 'video') 'encoded output did not contain a probeable video stream'

    $encodedInventory = Test-OutputVideoStreamPreservation -SourcePath $sourcePath -OutputPath $encodedPath -Route 'encode' -ExpectedVideoCodec 'mpeg4'
    Assert-True ([bool]$encodedInventory.Allowed) ("generated encode should satisfy executable video verification: {0}" -f $encodedInventory.Reason)
    Assert-True ($encodedInventory.schema_version -eq 'media_verification.v1') 'generated encode video evidence schema mismatch'
    $wrongCodecInventory = Test-OutputVideoStreamPreservation -SourcePath $sourcePath -OutputPath $encodedPath -Route 'encode' -ExpectedVideoCodec 'hevc'
    Assert-True (-not [bool]$wrongCodecInventory.Allowed) 'wrong selected encoder codec must block generated output verification'
    Assert-True ($wrongCodecInventory.ErrorCode -eq 'OUTPUT_VIDEO_STREAM_TOPOLOGY_MISMATCH') 'wrong selected encoder codec must use topology mismatch failure'

    $trackPlan = New-MediaTrackOutputVerificationPlan -AudioDecisions @(
        [pscustomobject]@{ audio_ordinal = 0; action = 'copy'; output_codec = 'aac'; language = 'und'; output_channels = 1; is_default = $false; is_forced = $false }
    )
    $trackResult = Test-MediaTrackOutputVerification -OutputPath $encodedPath -Plan $trackPlan
    Assert-True ([bool]$trackResult.allowed) ("generated encode should satisfy resolved audio verification: {0}; mismatches={1}" -f $trackResult.reason, ($trackResult.mismatches | ConvertTo-Json -Compress))
    $wrongLanguagePlan = New-MediaTrackOutputVerificationPlan -AudioDecisions @(
        [pscustomobject]@{ audio_ordinal = 0; action = 'copy'; output_codec = 'aac'; language = 'eng'; output_channels = 1; is_default = $false; is_forced = $false }
    )
    $wrongLanguageResult = Test-MediaTrackOutputVerification -OutputPath $encodedPath -Plan $wrongLanguagePlan
    Assert-True (-not [bool]$wrongLanguageResult.allowed) 'wrong audio language plan must block generated output verification'
    Assert-True ($wrongLanguageResult.error_code -eq 'OUTPUT_MEDIA_TRACK_VERIFICATION_FAILED') 'wrong audio language plan must use stable track-verification error'

    $outputJsonProbe = Invoke-FFprobeCommand -Stage 'integration-probe-output-json' -TimeoutSeconds 30 -ArgumentList @(
        '-v', 'error', '-show_streams', '-show_format', '-of', 'json', '--', $encodedPath
    )
    Assert-True ([int]$outputJsonProbe.ExitCode -eq 0) ("ffprobe streams/format JSON failed for generated output: {0}" -f $outputJsonProbe.Error)
    $outputJson = $outputJsonProbe.Output | ConvertFrom-Json -ErrorAction Stop
    Assert-True (@($outputJson.streams | Where-Object { $_.codec_type -eq 'video' }).Count -eq 1) 'generated output ffprobe JSON did not retain one real video stream'
    Assert-True (@($outputJson.streams | Where-Object { $_.codec_type -eq 'audio' }).Count -eq 1) 'generated output ffprobe JSON did not retain one audio stream'
    $frameProbe = Invoke-FFprobeCommand -Stage 'integration-probe-output-frames' -TimeoutSeconds 30 -ArgumentList @(
        '-v', 'error', '-read_intervals', '%+#1', '-select_streams', 'v:0', '-show_frames', '-of', 'json', '--', $encodedPath
    )
    Assert-True ([int]$frameProbe.ExitCode -eq 0) ("ffprobe frame JSON failed for generated output: {0}" -f $frameProbe.Error)
    $frameJson = $frameProbe.Output | ConvertFrom-Json -ErrorAction Stop
    Assert-True (@($frameJson.frames).Count -ge 1) 'generated output ffprobe frame JSON did not contain a video frame'
    $emptyOutputPath = Join-Path $workRoot 'interrupted-empty-output.mkv'
    [System.IO.File]::WriteAllText($emptyOutputPath, '', [System.Text.UTF8Encoding]::new($false))
    $emptyInventory = Test-OutputVideoStreamPreservation -SourcePath $sourcePath -OutputPath $emptyOutputPath -Route 'encode' -ExpectedVideoCodec 'mpeg4'
    Assert-True (-not [bool]$emptyInventory.Allowed) 'empty/interrupted output must fail video inventory verification'
    Assert-True ($emptyInventory.ErrorCode -eq 'OUTPUT_VIDEO_STREAM_PROBE_FAILED') 'empty/interrupted output must use output video probe failure'

    $completedEvents = @($script:IntegrationEvents | Where-Object { $_.EventType -eq 'tool_completed' })
    Assert-True (@($completedEvents | Where-Object { $_.Data.tool_name -eq 'ffmpeg' -and $_.Status -eq 'succeeded' }).Count -ge 2) 'ffmpeg wrapper/progress completion events were not recorded'
    Assert-True (@($completedEvents | Where-Object { $_.Data.tool_name -eq 'ffprobe' -and $_.Status -eq 'succeeded' }).Count -ge 2) 'ffprobe wrapper completion events were not recorded'

    $assPath = Join-Path $workRoot 'input.ass'
    $assMkv = Join-Path $workRoot 'ass-source.mkv'
    $assSrt = Join-Path $workRoot 'ass-output.srt'
    [System.IO.File]::WriteAllLines($assPath, @(
        '[Script Info]',
        'ScriptType: v4.00+',
        'PlayResX: 640',
        'PlayResY: 360',
        '',
        '[V4+ Styles]',
        'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
        'Style: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1',
        '',
        '[Events]',
        'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text',
        'Dialogue: 0,0:00:00.20,0:00:01.40,Default,,0,0,0,,Hello ASS integration'
    ), [System.Text.UTF8Encoding]::new($false))
    $assMux = Invoke-FFmpegCommand -Stage 'integration-ass-mux' -TimeoutSeconds 30 -ArgumentList @(
        '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'lavfi', '-i', 'testsrc=size=64x64:rate=5:duration=2',
        '-i', $assPath,
        '-map', '0:v', '-map', '1:s',
        '-c:v', 'mpeg4', '-q:v', '5',
        '-c:s', 'ass',
        '-t', '2',
        $assMkv
    )
    Assert-True ([int]$assMux.ExitCode -eq 0) ("ASS test mux failed: {0}" -f $assMux.Error)
    $assProbe = Invoke-FFprobeCommand -Stage 'integration-ass-probe' -TimeoutSeconds 30 -ArgumentList @(
        '-v', 'error', '-select_streams', 's',
        '-show_entries', 'stream=index,codec_name',
        '-of', 'json', '--', $assMkv
    )
    $assStreams = ([string]$assProbe.Output | ConvertFrom-Json).streams
    $assIndex = @($assStreams | Where-Object { $_.codec_name -eq 'ass' } | Select-Object -First 1).index
    Assert-True ($null -ne $assIndex) 'ASS integration source did not contain an ASS subtitle stream'
    $assConvert = $null
    $assConvertOk = $false
    $assConvertErrors = @()
    for ($attempt = 1; $attempt -le 2; $attempt++) {
        if (Test-Path -LiteralPath $assSrt -PathType Leaf) {
            Remove-Item -LiteralPath $assSrt -Force -ErrorAction SilentlyContinue
        }
        $assConvert = Invoke-PythonToolCommand -Stage 'integration-ass-convert' -TimeoutSeconds 60 -ArgumentList @(
            $assToSrtPath,
            '--input', $assMkv,
            '--stream-index', ([string]$assIndex),
            '--output', $assSrt,
            '--ffmpeg-bin', $ffmpegPath,
            '--include-styles', 'Default',
            '--quiet'
        )
        $assOutputOk = (Test-Path -LiteralPath $assSrt -PathType Leaf) -and ((Get-Content -LiteralPath $assSrt -Raw) -match 'Hello ASS integration')
        if ([int]$assConvert.ExitCode -eq 0 -and $assOutputOk) {
            $assConvertOk = $true
            break
        }
        $assConvertErrors += ("attempt {0}: exit={1}; error={2}" -f $attempt, [int]$assConvert.ExitCode, ([string]$assConvert.Error))
        Start-Sleep -Milliseconds 250
    }
    Assert-True $assConvertOk ("ASS helper conversion failed: {0}" -f ($assConvertErrors -join ' | '))

    $tx3gInputSrt = Join-Path $workRoot 'tx3g-input.srt'
    $tx3gMp4 = Join-Path $workRoot 'tx3g-source.mp4'
    $tx3gOutputSrt = Join-Path $workRoot 'tx3g-output.srt'
    [System.IO.File]::WriteAllText($tx3gInputSrt, "1`r`n00:00:00,200 --> 00:00:01,400`r`nHello TX3G integration`r`n", [System.Text.UTF8Encoding]::new($false))
    $tx3gMux = Invoke-FFmpegCommand -Stage 'integration-tx3g-mux' -TimeoutSeconds 30 -ArgumentList @(
        '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'lavfi', '-i', 'testsrc=size=64x64:rate=5:duration=2',
        '-i', $tx3gInputSrt,
        '-map', '0:v', '-map', '1:s',
        '-c:v', 'mpeg4', '-q:v', '5',
        '-c:s', 'mov_text',
        '-metadata:s:s:0', 'language=eng',
        '-t', '2',
        $tx3gMp4
    )
    Assert-True ([int]$tx3gMux.ExitCode -eq 0) ("TX3G test mux failed: {0}" -f $tx3gMux.Error)
    $tx3gProbe = Invoke-FFprobeCommand -Stage 'integration-tx3g-probe' -TimeoutSeconds 30 -ArgumentList @(
        '-v', 'error', '-select_streams', 's',
        '-show_entries', 'stream=index,codec_name,codec_tag_string',
        '-of', 'json', '--', $tx3gMp4
    )
    $tx3gStreams = ([string]$tx3gProbe.Output | ConvertFrom-Json).streams
    $tx3gStream = @($tx3gStreams | Where-Object { $_.codec_name -eq 'mov_text' -or $_.codec_tag_string -eq 'tx3g' } | Select-Object -First 1)
    Assert-True ($tx3gStream.Count -gt 0) 'TX3G integration source did not contain a tx3g/mov_text subtitle stream'
    $tx3gInfo = @{
        Stream = [pscustomobject]@{ index = [int]$tx3gStream[0].index }
        Lang = 'eng'
        Title = ''
        RawTitle = ''
        SubtitleOrdinal = 1
        SourceIsDefault = $false
        IsForced = $false
    }
    $tx3gExtract = Convert-Tx3gToSrt -SourceFile $tx3gMp4 -StreamIndex ([int]$tx3gStream[0].index) -StreamInfo $tx3gInfo -DestinationPath $tx3gOutputSrt -Context 'INTEGRATION: '
    Assert-True ([bool]$tx3gExtract.Ok) ("TX3G extraction failed: {0}" -f $tx3gExtract.Reason)
    Assert-True ([int]$tx3gExtract.CueCount -gt 0) 'TX3G extraction produced no cues'
    Assert-True ((Test-Path -LiteralPath $tx3gOutputSrt -PathType Leaf) -and ((Get-Content -LiteralPath $tx3gOutputSrt -Raw) -match 'Hello TX3G integration')) 'TX3G extraction did not produce expected SRT output'

    $script:BdpgsOcrToolPath = ''
    $missingBdpgsTool = Resolve-BdpgsOcrToolInvocation
    Assert-True (-not [bool]$missingBdpgsTool.Ok -and [string]$missingBdpgsTool.Reason -match 'not configured') 'BDPGS missing-tool check should classify an unconfigured OCR tool'
    $script:BdpgsOcrToolPath = 'Tools\PgsToSrt\PgsToSrt.exe'
    $bdpgsTool = Resolve-BdpgsOcrToolInvocation
    if (Test-Path -LiteralPath (Join-Path $pipelineRoot $script:BdpgsOcrToolPath) -PathType Leaf) {
        Assert-True ([bool]$bdpgsTool.Ok -and (Test-Path -LiteralPath $bdpgsTool.FilePath -PathType Leaf)) 'BDPGS OCR bundled tool resolution failed'
    }

    $script:processingDir = $workRoot
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

    $fakeBdpgsOcr = Join-Path $workRoot 'fake-pgs-to-srt.cmd'
    @'
@echo off
set "OUT="
:next
if "%~1"=="" goto done
if "%~1"=="--output" (
  set "OUT=%~2"
  shift
)
shift
goto next
:done
if "%OUT%"=="" exit /b 2
> "%OUT%" echo 1
>> "%OUT%" echo 00:00:00,200 --^> 00:00:01,400
>> "%OUT%" echo Hello BDPGS integration
>> "%OUT%" echo.
exit /b 0
'@ | Set-Content -LiteralPath $fakeBdpgsOcr -Encoding ASCII

    $bdpgsOutputSrt = Join-Path $workRoot 'bdpgs-output.srt'
    $script:BdpgsOcrToolPath = $fakeBdpgsOcr
    $script:BdpgsOcrTessdataPath = ''
    $bdpgsInfo = @{
        Stream = [pscustomobject]@{ index = 9 }
        Lang = 'eng'
        Title = 'English PGS'
        RawTitle = 'English PGS'
        SubtitleOrdinal = 1
        SourceIsDefault = $false
        IsForced = $false
    }
    $bdpgsConvert = Convert-BdpgsToSrt -SourceFile $encodedPath -StreamIndex 9 -StreamInfo $bdpgsInfo -DestinationPath $bdpgsOutputSrt -Context 'INTEGRATION: '
    Assert-True ([bool]$bdpgsConvert.Ok) ("BDPGS OCR conversion failed: {0}" -f $bdpgsConvert.Reason)
    Assert-True ([int]$bdpgsConvert.CueCount -gt 0) 'BDPGS OCR conversion produced no cues'
    Assert-True ((Test-Path -LiteralPath $bdpgsOutputSrt -PathType Leaf) -and ((Get-Content -LiteralPath $bdpgsOutputSrt -Raw) -match 'Hello BDPGS integration')) 'BDPGS OCR conversion did not produce expected SRT output'
    $bdpgsOcrEvents = @($script:IntegrationEvents | Where-Object { $_.EventType -eq 'tool_completed' -and $_.Data.tool_name -eq 'bdpgs-ocr' })
    Assert-True (@($bdpgsOcrEvents | Where-Object { $_.Status -eq 'succeeded' }).Count -ge 1) 'BDPGS OCR wrapper completion event was not recorded'

    $script:BdpgsOcrToolPath = Join-Path $workRoot 'missing-pgs-to-srt.exe'
    $bdpgsMissingTool = Convert-BdpgsToSrt -SourceFile $encodedPath -StreamIndex 10 -StreamInfo $bdpgsInfo -DestinationPath (Join-Path $workRoot 'bdpgs-missing-tool.srt') -Context 'INTEGRATION: '
    Assert-True (-not [bool]$bdpgsMissingTool.Ok) 'BDPGS missing-tool conversion unexpectedly succeeded'
    Assert-True ([string]$bdpgsMissingTool.Failure.ErrorCode -eq 'SUBTITLE_BDPGS_OCR_TOOL_MISSING') 'BDPGS missing-tool conversion was not classified'

    Write-Host 'Bundled FFmpeg/ffprobe/subtitle integration checks passed.'
} finally {
    $env:PYTHONPATH = $previousPythonPath
    Remove-Item -LiteralPath $StopFlag -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $PauseFlag -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue
}
