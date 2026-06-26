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

function Assert-Nearly {
    param([double] $Actual, [double] $Expected, [double] $Tolerance, [string] $Message)
    if ([math]::Abs($Actual - $Expected) -gt $Tolerance) {
        throw "$Message Expected '$Expected' +/- '$Tolerance', got '$Actual'."
    }
}

. (Join-Path $repoRoot 'ops\pipeline\engine\verify\quality.ps1')

$zeroWindows = Get-MediaQualitySampleWindows -DurationSeconds 0 -SampleSeconds 10 -SampleCount 3
Assert-True ($null -eq $zeroWindows) 'Zero-duration media should not produce sample windows.'
$shortWindows = Get-MediaQualitySampleWindows -DurationSeconds 40 -SampleSeconds 10 -SampleCount 3
Assert-True ($null -eq $shortWindows) 'Short media should fall back to full verification.'
$longWindows = @(Get-MediaQualitySampleWindows -DurationSeconds 3600 -SampleSeconds 10 -SampleCount 3)
Assert-Equal $longWindows.Count 3 'Long media should produce three sample windows.'
Assert-True ($longWindows[0] -ge 180) 'First sample should start after the first five percent of the file.'
Assert-True ($longWindows[2] -le 3410) 'Last sample should leave tail margin and sample duration.'
Assert-True ($longWindows[0] -lt $longWindows[1] -and $longWindows[1] -lt $longWindows[2]) 'Sample starts should be increasing.'
$singleWindow = @(Get-MediaQualitySampleWindows -DurationSeconds 100 -SampleSeconds 10 -SampleCount 1)
Assert-Equal $singleWindow.Count 1 'Single-count sample should produce one window.'
Assert-Nearly ([double]$singleWindow[0]) 45.0 0.001 'Single-count sample should use the midpoint.'

$refInfo = [pscustomobject][ordered]@{
    Width = 1920; Height = 1080; FrameRate = '24000/1001'; PixFmt = 'yuv420p'
}
$vmafGraph = New-MediaQualityFilterGraph -Metric 'vmaf' -RefInfo $refInfo -LogPath 'C:\Temp\a.json'
Assert-True ($vmafGraph.Contains('[0:v]')) 'VMAF graph should include distorted input branch.'
Assert-True ($vmafGraph.Contains('scale=1920:1080:flags=bicubic')) 'VMAF graph should scale distorted input to reference dimensions.'
Assert-True ($vmafGraph.Contains('fps=fps=24000/1001')) 'VMAF graph should align frame rate.'
Assert-True ($vmafGraph.Contains('format=yuv420p')) 'VMAF graph should align pixel format.'
Assert-True ($vmafGraph.Contains('log_path=C\\:/Temp/a.json')) 'VMAF graph should escape Windows log paths for lavfi.'
$ref10BitInfo = [pscustomobject][ordered]@{
    Width = 1920; Height = 1080; FrameRate = '24000/1001'; PixFmt = 'yuv420p10le'
}
$vmaf10BitGraph = New-MediaQualityFilterGraph -Metric 'vmaf' -RefInfo $ref10BitInfo -LogPath 'C:\Temp\a.json'
Assert-True ($vmaf10BitGraph.Contains('format=yuv420p10le')) '10-bit references should use 10-bit comparison format.'
$ssimGraph = New-MediaQualityFilterGraph -Metric 'ssim' -RefInfo $refInfo -LogPath 'C:\Temp\a.json'
Assert-True ($ssimGraph.EndsWith('ssim')) 'SSIM graph should end with the ssim filter.'
Assert-True (-not $ssimGraph.Contains('log_path=')) 'SSIM graph should not use a VMAF log path.'
$psnrGraph = New-MediaQualityFilterGraph -Metric 'psnr' -RefInfo $refInfo -LogPath 'C:\Temp\a.json'
Assert-True ($psnrGraph.EndsWith('psnr')) 'PSNR graph should end with the psnr filter.'
Assert-True (-not $psnrGraph.Contains('log_path=')) 'PSNR graph should not use a VMAF log path.'

$vmafLog = Join-Path ([System.IO.Path]::GetTempPath()) ("quality-vmaf-fixture-{0}.json" -f ([guid]::NewGuid().ToString('N')))
try {
    [System.IO.File]::WriteAllText($vmafLog, '{"pooled_metrics":{"vmaf":{"mean":91.5}}}', [System.Text.UTF8Encoding]::new($false))
    $vmafParsed = ConvertFrom-MediaQualityToolOutput -Metric 'vmaf' -LogJsonPath $vmafLog
    Assert-True ([bool]$vmafParsed.Ok) 'VMAF fixture should parse successfully.'
    Assert-Nearly ([double]$vmafParsed.Score) 91.5 0.001 'VMAF mean score mismatch.'
} finally {
    Remove-Item -LiteralPath $vmafLog -Force -ErrorAction SilentlyContinue
}
$missingVmafParsed = ConvertFrom-MediaQualityToolOutput -Metric 'vmaf' -LogJsonPath (Join-Path ([System.IO.Path]::GetTempPath()) 'missing-vmaf.json')
Assert-True (-not [bool]$missingVmafParsed.Ok) 'Missing VMAF JSON should be a parse failure.'
$ssimParsed = ConvertFrom-MediaQualityToolOutput -Metric 'ssim' -StdErrText 'n:1 Y:0.9 U:0.9 V:0.9 All:0.978 (16.5)'
Assert-True ([bool]$ssimParsed.Ok) 'SSIM stderr should parse successfully.'
Assert-Nearly ([double]$ssimParsed.Score) 0.978 0.000001 'SSIM score mismatch.'
$psnrParsed = ConvertFrom-MediaQualityToolOutput -Metric 'psnr' -StdErrText 'PSNR y:42.1 u:44.2 v:45.3 average:43.21 min:40 max:50'
Assert-True ([bool]$psnrParsed.Ok) 'PSNR stderr should parse successfully.'
Assert-Nearly ([double]$psnrParsed.Score) 43.21 0.001 'PSNR average mismatch.'
$psnrInfParsed = ConvertFrom-MediaQualityToolOutput -Metric 'psnr' -StdErrText 'PSNR y:inf u:inf v:inf average:inf min:inf max:inf'
Assert-True ([bool]$psnrInfParsed.Ok) 'Infinite PSNR stderr should parse successfully.'
Assert-Nearly ([double]$psnrInfParsed.Score) 100.0 0.001 'Infinite PSNR should normalize to 100.'

$passRecord = Resolve-MediaQualityOutcome -Record (New-MediaQualityVerificationRecord -Score 95 -Metric 'vmaf') -WarnThreshold 90 -FailThreshold 75 -FailAction 'warn_only'
Assert-Equal $passRecord['outcome'] 'pass' 'Score above thresholds should pass.'
Assert-True (-not [bool]$passRecord['block_publish']) 'Passing score must not block publish.'
$warnRecord = Resolve-MediaQualityOutcome -Record (New-MediaQualityVerificationRecord -Score 85 -Metric 'vmaf') -WarnThreshold 90 -FailThreshold 75 -FailAction 'warn_only'
Assert-Equal $warnRecord['outcome'] 'warn' 'Score below warn threshold should warn.'
Assert-True (-not [bool]$warnRecord['block_publish']) 'Warning score must not block publish.'
$warnOnlyFailRecord = Resolve-MediaQualityOutcome -Record (New-MediaQualityVerificationRecord -Score 70 -Metric 'vmaf') -WarnThreshold 90 -FailThreshold 75 -FailAction 'warn_only'
Assert-Equal $warnOnlyFailRecord['outcome'] 'fail' 'Score below fail threshold should fail.'
Assert-True (-not [bool]$warnOnlyFailRecord['block_publish']) 'warn_only fail action must not block publish.'
$blockRecord = Resolve-MediaQualityOutcome -Record (New-MediaQualityVerificationRecord -Score 70 -Metric 'vmaf') -WarnThreshold 90 -FailThreshold 75 -FailAction 'block_review'
Assert-Equal $blockRecord['outcome'] 'fail' 'Blocking score below fail threshold should fail.'
Assert-True ([bool]$blockRecord['block_publish']) 'block_review fail action should block publish.'
$warnOnlyToolErrorRecord = Resolve-MediaQualityOutcome -Record (New-MediaQualityVerificationRecord -Metric 'vmaf' -ToolError 'tool unavailable' -Outcome 'error') -WarnThreshold 90 -FailThreshold 75 -FailAction 'warn_only'
Assert-Equal $warnOnlyToolErrorRecord['outcome'] 'error' 'Tool errors should keep error outcome.'
Assert-True (-not [bool]$warnOnlyToolErrorRecord['block_publish']) 'warn_only tool errors must remain fail-open.'
$toolErrorRecord = Resolve-MediaQualityOutcome -Record (New-MediaQualityVerificationRecord -Metric 'vmaf' -ToolError 'tool unavailable' -Outcome 'error') -WarnThreshold 90 -FailThreshold 75 -FailAction 'block_review'
Assert-Equal $toolErrorRecord['outcome'] 'error' 'Tool errors should keep error outcome in block_review mode.'
Assert-True ([bool]$toolErrorRecord['block_publish']) 'block_review tool errors must block publish when no score is produced.'
$missingScoreRecord = Resolve-MediaQualityOutcome -Record (New-MediaQualityVerificationRecord -Metric 'vmaf' -Outcome 'error') -WarnThreshold 90 -FailThreshold 75 -FailAction 'block_review'
Assert-Equal $missingScoreRecord['outcome'] 'error' 'Missing quality scores should be an error outcome.'
Assert-True ([bool]$missingScoreRecord['block_publish']) 'block_review missing scores must block publish.'
$disabledThresholdRecord = Resolve-MediaQualityOutcome -Record (New-MediaQualityVerificationRecord -Score 1 -Metric 'vmaf') -WarnThreshold 0 -FailThreshold 0 -FailAction 'block_review'
Assert-Equal $disabledThresholdRecord['outcome'] 'pass' 'Zero thresholds should disable warning/fail floors.'
Assert-True (-not [bool]$disabledThresholdRecord['block_publish']) 'Zero thresholds must not block publish.'

$outputEvidencePath = Join-Path $repoRoot 'ops\pipeline\engine\paths\output_evidence.ps1'
. $outputEvidencePath
$qualityWarningSummary = New-MediaPipelineVerificationEvidence -QualityEvidence $warnOnlyFailRecord
Assert-True ($qualityWarningSummary['checks_run'] -contains 'quality_verification') 'Verification evidence should include quality check.'
Assert-True ($qualityWarningSummary['warnings'] -contains 'quality_warning') 'warn_only quality fail should be summarized as warning.'
Assert-True (-not ($qualityWarningSummary['blocking_failures'] -contains 'quality_below_floor')) 'warn_only quality fail should not be a blocking verification summary.'
$qualityBlockingSummary = New-MediaPipelineVerificationEvidence -QualityEvidence $blockRecord
Assert-True ($qualityBlockingSummary['blocking_failures'] -contains 'quality_below_floor') 'block_review quality fail should be a blocking verification summary.'
Assert-Equal $qualityBlockingSummary['quality_ref'] 'quality_verification.v1' 'Verification evidence should include quality schema ref.'

$loaderText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline\module_loader.ps1') -Raw
$encodePaths = @(
    (Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline\encode.ps1')
) + @(Get-ChildItem -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine\process') -Filter 'encode_*.ps1' | ForEach-Object { $_.FullName })
$encodeText = ($encodePaths | ForEach-Object { Get-Content -LiteralPath $_ -Raw }) -join "`n"
$publishText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine\publish\publish_completion.ps1') -Raw
Assert-True ($loaderText -match 'QualityVerify\.ps1') 'Module loader must include the quality verification module.'
Assert-True ($encodeText -match '\$script:LastQualityVerification\s*=\s*\$null') 'Encode must reset quality verification evidence per file.'
Assert-True ($encodeText -match 'Invoke-MediaQualityVerification') 'Encode must invoke quality verification when enabled.'
Assert-True ($encodeText -match 'ENCODE_QUALITY_VERIFICATION_FAILED') 'Encode must classify blocking verifier errors separately from below-floor scores.'
Assert-True ($encodeText -match 'verifier errors must be resolved') 'Encode should guide operators when block_review verifier errors block publish.'
Assert-True ($publishText -match '\[''quality_verification''\]\s*=\s*\$script:LastQualityVerification') 'Publish completion must add quality sidecar evidence.'

function DebugLog { param([string] $Message) }
function Write-Log { param([string] $Message, [string] $Level = 'INFO') }
function Set-ProgressStage {
    param(
        [string] $Stage,
        [string] $Status,
        [string] $Route,
        $Percent,
        [switch] $SaveNow
    )
}
function Format-NativeCommandLine {
    param([string] $FilePath, [array] $ArgumentList)
    return (($FilePath, @($ArgumentList)) -join ' ')
}
function Test-IsUncPath {
    param([string] $Path)
    return $false
}

$ffmpegPath = Join-Path $repoRoot 'ops\pipeline\tools\ffmpeg\bin\ffmpeg.exe'
$ffprobePath = Join-Path $repoRoot 'ops\pipeline\tools\ffmpeg\bin\ffprobe.exe'
if ((Test-Path -LiteralPath $ffmpegPath -PathType Leaf) -and (Test-Path -LiteralPath $ffprobePath -PathType Leaf)) {
    $filtersText = (& $ffmpegPath -hide_banner -filters 2>&1) | Out-String
    if ($filtersText -match '\blibvmaf\b') {
        $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("quality-live-{0}" -f ([guid]::NewGuid().ToString('N')))
        [System.IO.Directory]::CreateDirectory($tempRoot) | Out-Null
        try {
            $sourcePath = Join-Path $tempRoot 'source.mkv'
            $degradedPath = Join-Path $tempRoot 'degraded.mp4'
            & $ffmpegPath -hide_banner -loglevel error -y -f lavfi -i 'testsrc2=duration=2:size=320x180:rate=24' -an -c:v ffv1 -pix_fmt yuv420p $sourcePath
            Assert-Equal $LASTEXITCODE 0 'Synthetic source generation should succeed.'
            & $ffmpegPath -hide_banner -loglevel error -y -i $sourcePath -an -c:v mpeg4 -q:v 31 -pix_fmt yuv420p $degradedPath
            Assert-Equal $LASTEXITCODE 0 'Synthetic degraded encode should succeed.'

            . (Join-Path $repoRoot 'ops\pipeline\engine\shared\native_process_contracts.ps1')
            . (Join-Path $repoRoot 'ops\pipeline\engine\shared\native.ps1')
            $script:ffmpegPath = $ffmpegPath
            $script:ffprobePath = $ffprobePath
            $script:processingDir = $tempRoot
            $script:StopRequested = $false
            $script:StopFlag = Join-Path $tempRoot 'stop.flag'
            $script:OutputValidationProbeTimeoutSeconds = 15

            $identical = Invoke-MediaQualityVerification -ReferencePath $sourcePath -DistortedPath $sourcePath -Metric 'vmaf' -SampleMode 'full' -SampleSeconds 1 -SampleCount 1 -TimeoutSeconds 120
            $degraded = Invoke-MediaQualityVerification -ReferencePath $sourcePath -DistortedPath $degradedPath -Metric 'vmaf' -SampleMode 'full' -SampleSeconds 1 -SampleCount 1 -TimeoutSeconds 120
            Assert-True ([string]$identical['tool_error'] -eq '') "Identical synthetic VMAF should not report a tool error: $($identical['tool_error'])"
            Assert-True ([string]$degraded['tool_error'] -eq '') "Degraded synthetic VMAF should not report a tool error: $($degraded['tool_error'])"
            Assert-True ([double]$identical['score'] -gt [double]$degraded['score']) 'Identical synthetic source should score higher than degraded encode.'
        } finally {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host 'OK: quality verification checks passed.'
