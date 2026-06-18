[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))

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

$script:MediaVerificationLogs = @()
function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
    $script:MediaVerificationLogs = @($script:MediaVerificationLogs) + @([pscustomobject]@{
        Message = $Message
        Level   = $Level
    })
}

. (Join-Path $repoRoot 'ops\pipeline\engine\probe\media_probe.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\publish_result.ps1')

function Get-MediaDuration {
    param([string] $FilePath)
    if ($FilePath -eq 'source.mkv') { return 0.0 }
    if ($FilePath -eq 'output.mkv') { return 120.0 }
    return 0.0
}

$failedClosed = Test-DurationMatch -SourcePath 'source.mkv' -OutputPath 'output.mkv' -Label 'VERIFY'
Assert-True (-not [bool]$failedClosed) 'Source duration probe failure must fail verification closed.'
Assert-True (@($script:MediaVerificationLogs | Where-Object { $_.Level -eq 'ERROR' -and $_.Message -match 'source duration probe failed' }).Count -gt 0) 'Source probe failure should log as a verification error.'

function Get-MediaDuration {
    param([string] $FilePath)
    if ($FilePath -eq 'source.mkv') { return 120.0 }
    if ($FilePath -eq 'output.mkv') { return 120.25 }
    return 0.0
}

$matched = Test-DurationMatch -SourcePath 'source.mkv' -OutputPath 'output.mkv' -ToleranceSeconds 1.0 -Label 'VERIFY'
Assert-True ([bool]$matched) 'Valid duration match should still pass.'

$script:VideoInventoryProbeCase = 'single'
function global:Invoke-FFprobeCommand {
    param(
        [array]$ArgumentList,
        [int]$TimeoutSeconds = 30,
        [string]$Stage = ''
    )
    if ($Stage -ne 'source-video-stream-inventory') {
        return [pscustomobject]@{ ExitCode = 1; Output = ''; Error = 'unexpected ffprobe stage'; TimedOut = $false; Stopped = $false }
    }
    switch ($script:VideoInventoryProbeCase) {
        'single' {
            return [pscustomobject]@{
                ExitCode = 0
                Output = '{"streams":[{"index":0,"codec_name":"hevc","width":3840,"height":2160,"disposition":{"attached_pic":0}}]}'
                Error = ''
                TimedOut = $false
                Stopped = $false
            }
        }
        'multi' {
            return [pscustomobject]@{
                ExitCode = 0
                Output = '{"streams":[{"index":0,"codec_name":"hevc","width":3840,"height":2160,"disposition":{"attached_pic":0}},{"index":2,"codec_name":"h264","width":1920,"height":1080,"disposition":{"attached_pic":0}},{"index":5,"codec_name":"mjpeg","width":600,"height":900,"disposition":{"attached_pic":1}}]}'
                Error = ''
                TimedOut = $false
                Stopped = $false
            }
        }
        'tagged-cover' {
            return [pscustomobject]@{
                ExitCode = 0
                Output = '{"streams":[{"index":0,"codec_name":"h264","width":1920,"height":1080,"disposition":{"attached_pic":0}},{"index":5,"codec_name":"mjpeg","width":640,"height":360,"tags":{"filename":"cover.jpg","mimetype":"image/jpeg"}}]}'
                Error = ''
                TimedOut = $false
                Stopped = $false
            }
        }
        'attached-only' {
            return [pscustomobject]@{
                ExitCode = 0
                Output = '{"streams":[{"index":5,"codec_name":"mjpeg","width":600,"height":900,"disposition":{"attached_pic":1}}]}'
                Error = ''
                TimedOut = $false
                Stopped = $false
            }
        }
        default {
            return [pscustomobject]@{ ExitCode = 1; Output = ''; Error = 'ffprobe failed'; TimedOut = $false; Stopped = $false }
        }
    }
}

$script:VideoInventoryProbeCase = 'single'
$singleVideoPolicy = Test-SourceVideoStreamPublishPolicy -FilePath 'single.mkv' -Route 'remux'
Assert-True ([bool]$singleVideoPolicy.Allowed) "A single real video stream should remain eligible for publish validation. Reason: $($singleVideoPolicy.Reason)"
Assert-Equal ([int]$singleVideoPolicy.Inventory.RealVideoStreamCount) 1 'Single-video inventory count mismatch.'
Assert-Equal ([int]$singleVideoPolicy.Inventory.AttachedPicCount) 0 'Single-video attached-picture count mismatch.'

$script:VideoInventoryProbeCase = 'multi'
$multiVideoPolicy = Test-SourceVideoStreamPublishPolicy -FilePath 'multi.mkv' -Route 'encode'
Assert-True (-not [bool]$multiVideoPolicy.Allowed) 'Multiple real video streams must fail closed until per-stream routing exists.'
Assert-Equal ([string]$multiVideoPolicy.ErrorCode) 'SOURCE_VIDEO_STREAMS_UNVETTED' 'Multi-video policy should use the unvetted-stream error code.'
Assert-Equal ([int]$multiVideoPolicy.Inventory.RealVideoStreamCount) 2 'Multi-video inventory should exclude attached pictures from real video count.'
Assert-Equal ([int]$multiVideoPolicy.Inventory.AttachedPicCount) 1 'Attached pictures should be counted separately from real video streams.'

$script:VideoInventoryProbeCase = 'tagged-cover'
$taggedCoverPolicy = Test-SourceVideoStreamPublishPolicy -FilePath 'tagged-cover.mkv' -Route 'encode'
Assert-True ([bool]$taggedCoverPolicy.Allowed) "A Matroska cover image exposed as tagged mjpeg video should not block publish validation. Reason: $($taggedCoverPolicy.Reason)"
Assert-Equal ([int]$taggedCoverPolicy.Inventory.RealVideoStreamCount) 1 'Tagged cover image should be excluded from real video count.'
Assert-Equal ([int]$taggedCoverPolicy.Inventory.AttachedPicCount) 1 'Tagged cover image should count as an attached picture.'
Assert-Equal ([int]$taggedCoverPolicy.Inventory.AttachedPicStreams[0].Index) 5 'Tagged cover image stream index should be preserved in attached-picture inventory.'

$script:VideoInventoryProbeCase = 'attached-only'
$missingVideoPolicy = Test-SourceVideoStreamPublishPolicy -FilePath 'cover-only.mkv' -Route 'remux'
Assert-True (-not [bool]$missingVideoPolicy.Allowed) 'Attached pictures must not count as publishable video.'
Assert-Equal ([string]$missingVideoPolicy.ErrorCode) 'SOURCE_VIDEO_STREAM_MISSING' 'Missing real video should use the missing-video error code.'

$script:VideoInventoryProbeCase = 'failure'
$probeFailurePolicy = Test-SourceVideoStreamPublishPolicy -FilePath 'broken.mkv' -Route 'encode'
Assert-True (-not [bool]$probeFailurePolicy.Allowed) 'Video inventory probe failure must fail closed.'
Assert-Equal ([string]$probeFailurePolicy.ErrorCode) 'SOURCE_VIDEO_STREAM_PROBE_FAILED' 'Probe failure should use the probe-failed error code.'

$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-existing-output-' + [guid]::NewGuid().ToString('N'))
[System.IO.Directory]::CreateDirectory($tempDir) | Out-Null
try {
    $outputPath = Join-Path $tempDir 'Existing.mkv'
    [System.IO.File]::WriteAllBytes($outputPath, [byte[]](1, 2, 3, 4))
    $sourceFile = [pscustomobject]@{
        FullName = 'C:\Source\ExistingSource.mkv'
        Length   = 987654321L
    }

    $publishResult = New-ExistingOutputPublishResult -SourceFile $sourceFile -OutputPath $outputPath
    Assert-True ([bool]$publishResult.Ok) 'Existing-output publish result should be successful.'
    Assert-Equal $publishResult.PublishState 'published' 'Existing-output publish state mismatch.'
    Assert-Equal $publishResult.PublishMode 'existing-output' 'Existing-output publish mode mismatch.'
    Assert-Equal $publishResult.OutputPath $outputPath 'Existing-output path mismatch.'
    Assert-Equal $publishResult.OutputSizeBytes 4 'Existing-output size mismatch.'
    Assert-Equal $publishResult.SourcePath 'C:\Source\ExistingSource.mkv' 'Existing-output source path mismatch.'
    Assert-Equal $publishResult.SourceSizeBytes 987654321 'Existing-output source size mismatch.'
} finally {
    Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}

$remuxText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline\remux.ps1') -Raw
$encodeText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline\encode.ps1') -Raw
Assert-True ($remuxText -match '\$script:LastPublishResult\s*=\s*New-ExistingOutputPublishResult') 'Remux existing-output branch must set LastPublishResult.'
Assert-True ($encodeText -match '\$script:LastPublishResult\s*=\s*New-ExistingOutputPublishResult') 'Encode existing-output branch must set LastPublishResult.'
Assert-True ($remuxText -match 'Test-SourceVideoStreamPublishPolicy') 'Remux must run source video stream policy before FFmpeg/mkvmerge publish.'
Assert-True ($encodeText -match 'Test-SourceVideoStreamPublishPolicy') 'Encode must run source video stream policy before FFmpeg publish.'
Assert-True ($remuxText -match 'REMUX_AUDIO_TID_MAPPING_FAILED') 'Remux must fail closed when audio TID probing cannot cover expected tracks.'
Assert-True ($remuxText -notmatch 'skipping explicit default-track flags') 'Remux must not publish after skipping explicit audio default-track flags.'

Write-Host 'Media verification safety checks passed.'
