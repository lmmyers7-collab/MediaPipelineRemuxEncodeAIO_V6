[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
$ffmpegPath = Join-Path $repoRoot 'ops\pipeline\tools\ffmpeg\bin\ffmpeg.exe'
$ffprobePath = Join-Path $repoRoot 'ops\pipeline\tools\ffmpeg\bin\ffprobe.exe'

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

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
}

function Invoke-RequiredTool {
    param(
        [Parameter(Mandatory)] [string] $FilePath,
        [Parameter(Mandatory)] [array] $Arguments,
        [Parameter(Mandatory)] [string] $Label
    )

    $toolOutput = & $FilePath @Arguments 2>&1
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
    if ($exitCode -ne 0) {
        $details = (@($toolOutput) | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
        throw "$Label failed with exit $exitCode.$([Environment]::NewLine)$details"
    }
    return @($toolOutput)
}

function Get-RealVideoStreamCount {
    param([Parameter(Mandatory)] [string] $FilePath)

    $jsonText = & $ffprobePath @(
        '-v', 'error',
        '-select_streams', 'v',
        '-show_entries', 'stream=index,codec_name,width,height,disposition:stream_tags=filename,mimetype',
        '-of', 'json',
        '--',
        $FilePath
    )
    if ($LASTEXITCODE -ne 0) {
        throw "ffprobe video inventory failed for $FilePath"
    }
    $json = ($jsonText | Out-String) | ConvertFrom-Json -ErrorAction Stop
    $realVideo = @()
    foreach ($stream in @($json.streams)) {
        $attached = $false
        if ($stream.disposition -and $stream.disposition.PSObject.Properties['attached_pic']) {
            $attached = ([int]$stream.disposition.attached_pic -ne 0)
        }
        $mimeType = ''
        $fileName = ''
        if ($stream.tags) {
            if ($stream.tags.PSObject.Properties['mimetype']) { $mimeType = ([string]$stream.tags.mimetype).ToLowerInvariant() }
            if ($stream.tags.PSObject.Properties['filename']) { $fileName = ([string]$stream.tags.filename).ToLowerInvariant() }
        }
        if (-not $attached -and $mimeType.StartsWith('image/')) { $attached = $true }
        if (-not $attached -and $fileName -match '\.(jpg|jpeg|png|webp|bmp)$') { $attached = $true }
        if (-not $attached) { $realVideo += @($stream) }
    }
    return [int]$realVideo.Count
}

Assert-True (Test-Path -LiteralPath $ffmpegPath -PathType Leaf) "Bundled ffmpeg is missing: $ffmpegPath"
Assert-True (Test-Path -LiteralPath $ffprobePath -PathType Leaf) "Bundled ffprobe is missing: $ffprobePath"

. (Join-Path $repoRoot 'ops\pipeline\engine\shared\media_constants.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\config\choice_registry.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\config\default_values.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\decide\encoder_descriptors.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\decide\encode_policy.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\process\remux_ffmpeg_av_stage.ps1')

$workRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-fr016-topology-' + [guid]::NewGuid().ToString('N'))
[System.IO.Directory]::CreateDirectory($workRoot) | Out-Null

try {
    $multiSource = Join-Path $workRoot 'fr016_two_real_video_source.mkv'
    $remuxOut = Join-Path $workRoot 'fr016_remux_preserve_all.mkv'
    $encodeOut = Join-Path $workRoot 'fr016_encode_preserve_all.mkv'
    $tdarrSeed = Join-Path $repoRoot 'LocalBase\TdarrFixScratch\tdarr-0253-genpts.mkv'
    $sourceOrigin = 'generated-lavfi'

    if (Test-Path -LiteralPath $tdarrSeed -PathType Leaf) {
        $sourceOrigin = 'tdarr-derived'
        Invoke-RequiredTool -FilePath $ffmpegPath -Label 'derive two-video Tdarr source' -Arguments @(
            '-hide_banner', '-loglevel', 'error', '-y',
            '-i', $tdarrSeed,
            '-t', '3',
            '-map', '0:v:0',
            '-map', '0:v:0',
            '-map', '0:a:0?',
            '-c', 'copy',
            $multiSource
        ) | Out-Null
    } else {
        Invoke-RequiredTool -FilePath $ffmpegPath -Label 'generate two-video source' -Arguments @(
            '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=12:duration=3',
            '-f', 'lavfi', '-i', 'testsrc=size=128x72:rate=12:duration=3',
            '-f', 'lavfi', '-i', 'sine=frequency=1000:duration=3',
            '-map', '0:v:0',
            '-map', '1:v:0',
            '-map', '2:a:0',
            '-c:v', 'mpeg4',
            '-q:v', '5',
            '-c:a', 'aac',
            '-shortest',
            $multiSource
        ) | Out-Null
    }

    Assert-Equal (Get-RealVideoStreamCount -FilePath $multiSource) 2 'Representative source should contain two real video streams.'

    Invoke-RequiredTool -FilePath $ffmpegPath -Label 'remux preserve-all topology' -Arguments @(
        '-hide_banner', '-loglevel', 'error', '-y',
        '-fflags', '+genpts',
        '-i', $multiSource,
        '-map', '0:V',
        '-c:v', 'copy',
        '-map', '0:a?',
        '-c:a', 'copy',
        '-map', '0:t?',
        '-map_chapters', '0',
        '-map_metadata', '0',
        $remuxOut
    ) | Out-Null

    Assert-Equal (Get-RealVideoStreamCount -FilePath $remuxOut) 2 'Remux topology should preserve both real video streams.'

    $encodeArgs = New-EncodeFfmpegArgumentList `
        -InputPath $multiSource `
        -GlobalTitle 'FR-016 topology proof' `
        -VideoFlags @('-c:v', 'mpeg4', '-q:v', '5') `
        -AudioArgs @('-map', '0:a?', '-c:a', 'copy') `
        -SubtitleMapArgs @() `
        -VideoFilterArgs @() `
        -OutputPath $encodeOut
    $encodedArgText = @($encodeArgs) -join '|'
    Assert-True ($encodedArgText -match '(^|\|)-map\|0:V(\||$)') 'Encode argument builder must map all real video streams with 0:V.'
    Assert-True ($encodedArgText -notmatch '0:v:0') 'Encode argument builder must not map only the first video stream.'

    Invoke-RequiredTool -FilePath $ffmpegPath -Label 'encode preserve-all topology' -Arguments (@('-hide_banner', '-loglevel', 'error', '-y') + @($encodeArgs)) | Out-Null
    Assert-Equal (Get-RealVideoStreamCount -FilePath $encodeOut) 2 'Encode topology should preserve both real video streams.'

    $remuxVideoArgs = New-MediaPipelineRemuxVideoArgumentList -Context ([pscustomobject]@{
        LocalIn            = $multiSource
        SourceCodec        = 'hevc'
        VideoStreamPolicy  = [pscustomobject]@{
            Inventory = [pscustomobject]@{
                Ok                   = $true
                ErrorCode            = ''
                Reason               = ''
                RealVideoStreams     = @(
                    [pscustomobject]@{ Index = 0; VideoOrdinal = 0; Codec = 'hevc'; Width = 160; Height = 90; AttachedPicture = $false },
                    [pscustomobject]@{ Index = 2; VideoOrdinal = 1; Codec = 'h264'; Width = 128; Height = 72; AttachedPicture = $false }
                )
                AttachedPicStreams   = @(
                    [pscustomobject]@{ Index = 5; VideoOrdinal = -1; Codec = 'mjpeg'; Width = 600; Height = 900; AttachedPicture = $true }
                )
                RealVideoStreamCount = 2
                AttachedPicCount     = 1
            }
        }
    })
    $remuxVideoArgText = @($remuxVideoArgs) -join '|'
    Assert-True ($remuxVideoArgText -match '(^|\|)-map\|0:0\|-map\|0:2\|-map\|0:5\|-c:v\|copy(\||$)') 'Remux video arg builder must preserve all inventory video streams with explicit maps.'
    Assert-True ($remuxVideoArgText -match '(^|\|)-bsf:v:0\|hevc_mp4toannexb(\||$)') 'Remux video arg builder must scope HEVC bitstream filtering to the HEVC output ordinal.'
    Assert-True ($remuxVideoArgText -notmatch '(^|\|)-bsf:v\|hevc_mp4toannexb(\||$)') 'Remux video arg builder must not emit a broad HEVC bitstream filter.'
    Assert-True ($remuxVideoArgText -notmatch '(^|\|)-bsf:v:1\|hevc_mp4toannexb(\||$)') 'Remux video arg builder must not apply HEVC filtering to non-HEVC alternate video.'
    Assert-True ($remuxVideoArgText -notmatch '(^|\|)-bsf:v:2\|hevc_mp4toannexb(\||$)') 'Remux video arg builder must not apply HEVC filtering to MJPEG cover-art output.'
    Assert-True ($remuxVideoArgText -notmatch '(^|\|)-bsf:v:5\|hevc_mp4toannexb(\||$)') 'Remux video arg builder must not treat source indexes as output filter ordinals.'

    Write-Host "FR-016 multi-video topology checks passed. SourceOrigin=$sourceOrigin source=2 remux=2 encode=2"
} finally {
    Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue
}
