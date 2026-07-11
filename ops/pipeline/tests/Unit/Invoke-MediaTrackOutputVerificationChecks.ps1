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
    if ($Actual -ne $Expected) { throw "$Message Expected '$Expected', got '$Actual'." }
}

$script:TrackVerificationProbeOutput = ''
$script:TrackVerificationLastArgumentList = @()
function global:Invoke-FFprobeCommand {
    param([array] $ArgumentList, [int] $TimeoutSeconds = 30, [string] $Stage = '')
    if ($Stage -ne 'media-track-output-verify') {
        return [pscustomobject]@{ ExitCode = 1; Output = ''; Error = "Unexpected stage: $Stage"; TimedOut = $false; Stopped = $false }
    }
    $script:TrackVerificationLastArgumentList = @($ArgumentList)
    return [pscustomobject]@{ ExitCode = 0; Output = $script:TrackVerificationProbeOutput; Error = ''; TimedOut = $false; Stopped = $false }
}

. (Join-Path $repoRoot 'ops\pipeline\engine\verify\media_track_verification.ps1')

$plan = New-MediaTrackOutputVerificationPlan `
    -AudioDecisions @(
        [pscustomobject]@{ audio_ordinal = 0; action = 'transcode'; output_codec = 'eac3'; output_channels = 6; language = 'eng'; is_default = $true; is_forced = $false },
        [pscustomobject]@{ audio_ordinal = 1; action = 'copy'; output_codec = 'aac'; output_channels = 2; language = 'jpn'; is_default = $false; is_forced = $false },
        [pscustomobject]@{ audio_ordinal = $null; action = 'drop'; output_codec = ''; output_channels = 0; language = 'eng'; is_default = $false; is_forced = $false }
    ) `
    -SubtitleTracks @(
        [pscustomobject]@{ output_location = 'embedded'; output_codec = 'subrip'; language = 'eng'; is_default = $false; is_forced = $true; source_stream_index = 4; action = 'convert_bdpgs' },
        [pscustomobject]@{ output_location = 'external_sidecar'; output_codec = 'subrip'; language = 'jpn'; is_default = $false; is_forced = $false; source_stream_index = 5; action = 'convert_tx3g' }
    )

Assert-Equal $plan.schema_version 'media_track_verification_plan.v1' 'Verification plan schema mismatch.'
Assert-Equal @($plan.expected_audio_tracks).Count 2 'Dropped audio must not become an expected output track.'
Assert-Equal @($plan.expected_embedded_subtitle_tracks).Count 1 'External subtitle sidecars must not be expected as embedded tracks.'
Assert-Equal @($plan.expected_external_subtitle_tracks).Count 1 'External sidecar evidence must remain explicit in the plan.'

$ffmpegPlan = New-MediaTrackOutputVerificationPlanFromFfmpegSubtitleArgs `
    -AudioDecisions @([pscustomobject]@{ audio_ordinal = 0; action = 'copy'; output_codec = 'eac3'; output_channels = 6; language = 'eng'; is_default = $true; is_forced = $false }) `
    -SubtitleMapArgs @('-map','0:4','-c:s:0','subrip','-metadata:s:s:0','language=eng','-disposition:s:0','forced')
Assert-Equal @($ffmpegPlan.expected_embedded_subtitle_tracks).Count 1 'FFmpeg subtitle map args must produce one embedded verification expectation.'
Assert-Equal ([string]$ffmpegPlan.expected_embedded_subtitle_tracks[0].codec) 'subrip' 'FFmpeg subtitle codec expectation drifted.'
Assert-True ([bool]$ffmpegPlan.expected_embedded_subtitle_tracks[0].is_forced) 'FFmpeg subtitle forced disposition must be preserved in the verification plan.'

$script:TrackVerificationProbeOutput = '{"streams":[' +
    '{"index":0,"codec_type":"audio","codec_name":"eac3","channels":6,"tags":{"language":"eng"},"disposition":{"default":1,"forced":0}},' +
    '{"index":1,"codec_type":"audio","codec_name":"aac","channels":2,"tags":{"language":"jpn"},"disposition":{"default":0,"forced":0}},' +
    '{"index":2,"codec_type":"subtitle","codec_name":"subrip","tags":{"language":"eng"},"disposition":{"default":0,"forced":1}}' +
']} '
$verified = Test-MediaTrackOutputVerification -OutputPath 'matching-output.mkv' -Plan $plan
Assert-True ([bool]$verified.allowed) "Matching planned audio/subtitle topology should pass: $($verified.reason)"
Assert-Equal @($verified.mismatches).Count 0 'Matching topology must not produce mismatch evidence.'
Assert-True ($script:TrackVerificationLastArgumentList -contains 'stream=index,codec_type,codec_name,channels:stream_tags=language,title:stream_disposition=default,forced') 'Output verifier must explicitly request ffprobe default/forced dispositions.'

$script:TrackVerificationProbeOutput = '{"streams":[' +
    '{"index":0,"codec_type":"audio","codec_name":"eac3","channels":2,"tags":{"language":"eng"},"disposition":{"default":0,"forced":0}},' +
    '{"index":1,"codec_type":"subtitle","codec_name":"subrip","tags":{"language":"fra"},"disposition":{"default":0,"forced":0}}' +
']} '
$mismatched = Test-MediaTrackOutputVerification -OutputPath 'mismatched-output.mkv' -Plan $plan
Assert-True (-not [bool]$mismatched.allowed) 'Lost audio/subtitle topology must block publish verification.'
Assert-Equal $mismatched.error_code 'OUTPUT_MEDIA_TRACK_VERIFICATION_FAILED' 'Mismatch must use the stable media-track failure code.'
Assert-True (@($mismatched.mismatches | Where-Object { $_.kind -eq 'audio' -and $_.property -eq 'channels' }).Count -gt 0) 'Audio channel mismatch must be surfaced.'
Assert-True (@($mismatched.mismatches | Where-Object { $_.kind -eq 'audio' -and $_.property -eq 'count' }).Count -gt 0) 'Lost audio track count must be surfaced.'
Assert-True (@($mismatched.mismatches | Where-Object { $_.kind -eq 'subtitle' -and $_.property -eq 'language' }).Count -gt 0) 'Subtitle language mismatch must be surfaced.'
Assert-True (@($mismatched.mismatches | Where-Object { $_.kind -eq 'subtitle' -and $_.property -eq 'forced' }).Count -gt 0) 'Lost forced disposition must be surfaced.'

$script:TrackVerificationProbeOutput = '{not json}'
$invalidProbe = Test-MediaTrackOutputVerification -OutputPath 'invalid-output.mkv' -Plan $plan
Assert-True (-not [bool]$invalidProbe.allowed) 'Invalid output ffprobe JSON must fail closed.'
Assert-Equal $invalidProbe.error_code 'OUTPUT_MEDIA_TRACK_PROBE_INVALID' 'Invalid output ffprobe JSON must use a stable code.'

Write-Host 'Media track output verification checks passed.'
