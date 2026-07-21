param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
}

function DebugLog {
    param([string] $Message)
}

$script:AudioProgressCalls = [System.Collections.Generic.List[object]]::new()
$script:AudioPolicySeedCalls = [System.Collections.Generic.List[object]]::new()
function Set-MediaPipelineRunMonitorAudioRecords {
    param(
        [string] $RunId,
        [string] $JobId,
        [array] $Records,
        [switch] $FinalPolicy
    )
    $script:AudioPolicySeedCalls.Add([pscustomobject]@{
        RunId = $RunId
        JobId = $JobId
        Records = @($Records)
        FinalPolicy = [bool]$FinalPolicy
    }) | Out-Null
}
function Set-ProgressAudioTrack {
    param(
        [int] $StreamIndex = -1,
        [string] $Stage,
        [string] $Status,
        [string] $AudioAction,
        [string] $SourceCodec,
        $SourceChannels,
        [string] $OutputCodec,
        $OutputChannels,
        [string] $Language,
        [string] $Reason,
        [int] $StepIndex,
        [int] $StepTotal,
        [string] $Detail,
        [switch] $Completed,
        [switch] $Failed,
        [switch] $SaveNow
    )
    $script:AudioProgressCalls.Add([pscustomobject]@{
        StreamIndex = $StreamIndex
        Stage = $Stage
        AudioAction = $AudioAction
        PolicySeeded = ($script:AudioPolicySeedCalls.Count -gt 0)
    }) | Out-Null
}

function Assert-True {
    param(
        [bool] $Condition,
        [string] $Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param(
        $Actual,
        $Expected,
        [string] $Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected' but got '$Actual'."
    }
}

function Assert-SequenceEqual {
    param(
        [array] $Actual,
        [array] $Expected,
        [string] $Message
    )

    if ($Actual.Count -ne $Expected.Count) {
        throw "$Message Expected $($Expected.Count) items but got $($Actual.Count). Actual: $($Actual -join '|')"
    }
    for ($i = 0; $i -lt $Expected.Count; $i++) {
        if ([string]$Actual[$i] -ne [string]$Expected[$i]) {
            throw "$Message Difference at index $i. Expected '$($Expected[$i])' but got '$($Actual[$i])'. Actual: $($Actual -join '|')"
        }
    }
}

function Resolve-MediaPipelineAudioPassthroughProfile {
    param(
        [string] $Profile,
        [array] $LegacyCompatibleAudioCodecs = @()
    )

    $normalized = if ($Profile) { $Profile.Trim().ToLowerInvariant() } else { '' }
    if ($normalized -in @('plex_balanced','compatibility','lossless_passthrough','custom_codec_list')) {
        return $normalized
    }
    if (@($LegacyCompatibleAudioCodecs).Count -gt 0) { return 'custom_codec_list' }
    return 'plex_balanced'
}

function Get-MediaPipelineAudioPassthroughProfileCodecs {
    param([string] $Profile)

    switch (($Profile ?? '').Trim().ToLowerInvariant()) {
        'compatibility'         { return @('aac','ac3','eac3') }
        'lossless_passthrough'  { return @('aac','ac3','eac3','truehd','flac','dts') }
        'plex_balanced'         { return @('aac','ac3','eac3','mp3','opus','vorbis') }
        default                 { return @() }
    }
}

function Get-MediaAudioCodecFlacName { return 'flac' }

function Get-MediaAudioCodecFidelityRankValue {
    param([string] $Codec)

    switch (($Codec ?? '').Trim().ToLowerInvariant()) {
        'truehd'    { return 90 }
        'flac'      { return 85 }
        'pcm_s16le' { return 80 }
        'eac3'      { return 70 }
        'ac3'       { return 60 }
        'aac'       { return 50 }
        default     { return 10 }
    }
}

function Get-MediaAudioCodecDisplayLabel {
    param([string] $Codec)

    switch (($Codec ?? '').Trim().ToLowerInvariant()) {
        'eac3'      { return 'EAC3' }
        'ac3'       { return 'AC3' }
        'aac'       { return 'AAC' }
        'truehd'    { return 'TrueHD' }
        'flac'      { return 'FLAC' }
        'pcm_s16le' { return 'PCM' }
        default     { return ($Codec ?? '').ToUpperInvariant() }
    }
}

$script:AudioOverride = $null
function Get-FileOverrideAudioSettings { return $script:AudioOverride }

function Test-AudioTrackKeptByOverride {
    param(
        [string] $Language,
        [int] $Channels,
        [string] $Title,
        [string] $Codec = '',
        $StreamIndex = $null,
        [object] $AudioOverride
    )

    if ($AudioOverride -and $AudioOverride.keep_languages) {
        return @($AudioOverride.keep_languages) -contains $Language
    }
    return $true
}

function Get-AudioTrackTitleOverride {
    param(
        [string] $Language,
        [int] $Channels,
        [object] $AudioOverride
    )

    if ($AudioOverride -and $AudioOverride.title_override -and $Language -eq 'jpn') {
        return [string]$AudioOverride.title_override
    }
    return ''
}

function Invoke-FFprobeCommand {
    param(
        [string[]] $ArgumentList,
        [int] $TimeoutSeconds,
        [string] $Stage
    )

    $joined = $ArgumentList -join '|'
    if ($script:ProbeMode -eq 'metadata-failed') {
        if ($joined -match 'stream=index,codec_name') {
            return [pscustomobject]@{ ExitCode = 1; Output = ''; Error = 'metadata probe failed'; TimedOut = $false; Stopped = $false }
        }
        if ($joined -match 'stream=codec_type') {
            return [pscustomobject]@{ ExitCode = 0; Output = 'audio'; Error = ''; TimedOut = $false; Stopped = $false }
        }
    }
    if ($script:ProbeMode -eq 'missing') {
        if ($joined -match 'default=noprint_wrappers') {
            return [pscustomobject]@{ ExitCode = 0; Output = ''; Error = ''; TimedOut = $false; Stopped = $false }
        }
        return [pscustomobject]@{ ExitCode = 0; Output = (@{ streams = @() } | ConvertTo-Json -Depth 4); Error = ''; TimedOut = $false; Stopped = $false }
    }
    if ([string]$script:ProbeMode -match '^presence-(nonzero|timedout|stopped)$') {
        if ($joined -match 'default=noprint_wrappers') {
            switch ($script:ProbeMode) {
                'presence-nonzero' { return [pscustomobject]@{ ExitCode = 1; Output = ''; Error = 'presence probe failed'; TimedOut = $false; Stopped = $false } }
                'presence-timedout' { return [pscustomobject]@{ ExitCode = -1; Output = ''; Error = 'presence probe timed out'; TimedOut = $true; Stopped = $false } }
                'presence-stopped' { return [pscustomobject]@{ ExitCode = -1; Output = ''; Error = 'presence probe stopped'; TimedOut = $false; Stopped = $true } }
            }
        }
        return [pscustomobject]@{ ExitCode = 0; Output = (@{ streams = @() } | ConvertTo-Json -Depth 4); Error = ''; TimedOut = $false; Stopped = $false }
    }

    $payload = @{
        streams = @(
            @{ index = 4; codec_name = 'ac3'; channels = 6; channel_layout = '5.1(side)'; tags = @{ language = 'en'; title = 'Director Commentary' }; disposition = @{ forced = 0; default = 1 } },
            @{ index = 9; codec_name = 'pcm_s16le'; channels = 2; channel_layout = 'stereo'; tags = @{ language = 'jpn'; title = '' }; disposition = @{ forced = 1; default = 0 } },
            @{ index = 15; codec_name = 'truehd'; channels = 8; channel_layout = '7.1'; tags = @{ language = 'english'; title = 'Main Audio' }; disposition = @{ forced = 0; default = 0 } }
        )
    }
    return [pscustomobject]@{ ExitCode = 0; Output = ($payload | ConvertTo-Json -Depth 8); Error = ''; TimedOut = $false; Stopped = $false }
}

. (Join-Path $repoRoot 'ops\pipeline\engine\audio\audio.ps1')

$script:PreferredDefaultAudioLanguages = @('jpn', 'eng')
$script:AudioPassthroughProfile = 'custom_codec_list'
$script:CompatibleAudioCodecs = @('ac3', 'eac3', 'aac', 'truehd', 'flac')
$script:AudioTranscodeCodec = 'eac3'
$script:AudioTranscodeBitrate = '640k'
$script:AudioTranscodeAutoBitrateByChannels = $false
$script:AudioDownmixMode = 'max_channels'
$script:AudioMaxChannels = 6
$script:AllowNoAudio = $false
$script:ProbeMode = 'normal'
$script:PipelineRunId = 'audio-policy-run'
$script:CurrentRunMonitorJobId = 'audio-policy-run:item:1'

Assert-True (Test-IsPcmAudioCodec 'pcm_s16le') 'pcm_s16le was not detected as PCM audio.'
Assert-True (Test-IsPcmAudioCodec 'A_PCM/INT/LIT') 'A_PCM/INT/LIT was not detected as PCM audio.'
Assert-True (-not (Test-IsPcmAudioCodec 'eac3')) 'EAC3 was incorrectly detected as PCM audio.'

$script:AllowNoAudio = 'false'
Assert-True (-not (Get-EffectiveAllowNoAudio)) 'String AllowNoAudio=false should not enable no-audio output.'
$script:AllowNoAudio = 'yes'
Assert-True (Get-EffectiveAllowNoAudio) 'String AllowNoAudio=yes should enable no-audio output.'
$script:ActiveOverrides = @{ AllowNoAudio = 'off' }
Assert-True (-not (Get-EffectiveAllowNoAudio)) 'String ActiveOverrides AllowNoAudio=off should not enable no-audio output.'
$script:ActiveOverrides = @{ FlacAsCompatible = 'false' }
$script:CompatibleAudioCodecs = @('aac')
Assert-SequenceEqual (Get-EffectiveCompatibleAudioCodecs) @('aac') 'String FlacAsCompatible=false should not add FLAC passthrough.'
$script:ActiveOverrides = @{ FlacAsCompatible = 'true' }
Assert-SequenceEqual (Get-EffectiveCompatibleAudioCodecs) @('aac','flac') 'String FlacAsCompatible=true should add FLAC passthrough.'
$script:ActiveOverrides = @{}
$script:AllowNoAudio = $false
$script:CompatibleAudioCodecs = @('ac3', 'eac3', 'aac', 'truehd', 'flac')

$script:AudioTranscodeBitrate = '0k'
Assert-Equal (Get-EffectiveAudioTranscodeBitrate) '640k' 'Invalid zero audio transcode bitrate should fall back to the default.'
$script:ActiveOverrides = @{ AudioTranscodeBitrate = '0k' }
Assert-Equal (Get-EffectiveAudioTranscodeBitrate) '640k' 'Invalid zero override audio transcode bitrate should fall back to the default.'
$script:ActiveOverrides = @{}
$script:AudioTranscodeBitrate = '640k'

$expectedArgs = @(
    '-map','0:a:0',
    '-map','0:a:1',
    '-map','0:a:2',
    '-c:a:0','copy',
    '-metadata:s:a:0','language=eng',
    '-metadata:s:a:0','title=English - 5.1 AC3 [Commentary]',
    '-c:a:1','eac3',
    '-b:a:1','640k',
    '-ac:1','2',
    '-channel_layout:a:1','stereo',
    '-metadata:s:a:1','language=jpn',
    '-metadata:s:a:1','title=Japanese - 2.0 EAC3',
    '-c:a:2','copy',
    '-metadata:s:a:2','language=eng',
    '-metadata:s:a:2','title=English - 7.1 TrueHD',
    '-disposition:a:0','0',
    '-disposition:a:1','forced',
    '-disposition:a:2','0',
    '-disposition:a:1','default+forced'
)
$audioArgs = @(Build-AudioArgs 'source.mkv')
Assert-SequenceEqual $audioArgs $expectedArgs 'Build-AudioArgs changed FFmpeg audio arguments.'
$policyProgressStreamIndexes = @($script:AudioProgressCalls | Where-Object { $_.Stage -eq 'audio_policy' -and $_.StreamIndex -ge 0 } | ForEach-Object { $_.StreamIndex })
Assert-SequenceEqual $policyProgressStreamIndexes @(4, 9, 15) 'Audio monitor evidence must use exact ffprobe source stream indexes while FFmpeg map ordinals stay unchanged.'
Assert-Equal $script:AudioPolicySeedCalls.Count 1 'Audio policy must seed the exact Run Monitor tracks once before emitting per-track progress.'
Assert-True ([bool](@($script:AudioProgressCalls | Where-Object { $_.Stage -eq 'audio_policy' -and $_.StreamIndex -ge 0 -and -not $_.PolicySeeded }).Count -eq 0)) 'Per-track audio progress must never run before exact backend track records exist.'
Assert-Equal $script:LastAudioDefaultIndex 1 'Default audio index changed.'
Assert-Equal $script:LastAudioTrackCount 3 'Audio track count changed.'
Assert-True $script:LastAudioTranscodeActive 'Audio transcode-active flag was not set.'
$audioDecisions = @(Get-LastAudioDecisionRecords)
Assert-Equal $audioDecisions.Count 3 'Audio decision record count changed.'
Assert-Equal $audioDecisions[0].action 'copy' 'Copied commentary audio decision not recorded.'
Assert-True $audioDecisions[0].is_commentary 'Commentary flag changed.'
Assert-Equal $audioDecisions[1].action 'transcode' 'PCM action changed.'
Assert-Equal $audioDecisions[1].reason 'PCM standardization' 'PCM transcode reason changed.'
Assert-True $audioDecisions[1].is_default 'Preferred forced Japanese track was not recorded as default.'
Assert-Equal $audioDecisions[1].source_layout 'stereo' 'Audio source layout should retain ffprobe evidence.'
Assert-Equal $audioDecisions[1].output_layout 'stereo' 'Transcoded audio output layout should retain the backend-authored FFmpeg layout.'
Assert-Equal $audioDecisions[1].planned_action 'transcode' 'Audio planned transcode action should be explicit.'
Assert-Equal $audioDecisions[1].reason_code 'pcm_standardization' 'Audio policy should retain a stable transcode reason code.'
Assert-Equal $audioDecisions[2].output_codec 'truehd' 'TrueHD copy output codec decision changed.'
Assert-Equal $audioDecisions[2].passthrough_profile 'custom_codec_list' 'Passthrough profile was not recorded.'
Assert-Equal $audioDecisions[2].output_layout '7.1' 'Passthrough audio output layout should retain the probed source layout.'
Assert-Equal $audioDecisions[2].planned_action 'passthrough' 'Audio passthrough planned action should be explicit.'

$script:OutputContainer = 'mp4'
$mp4Args = @(Build-AudioArgs 'source.mkv')
Assert-SequenceEqual $mp4Args @(
    '-map','0:a:1',
    '-c:a:0','eac3',
    '-b:a:0','640k',
    '-ac:0','2',
    '-channel_layout:a:0','stereo',
    '-metadata:s:a:0','language=jpn',
    '-disposition:a:0','forced',
    '-disposition:a:0','default+forced'
) 'MP4 compatibility should keep exactly one preferred-language EAC3 audio stream without title metadata.'
$mp4Decisions = @(Get-LastAudioDecisionRecords)
Assert-Equal $mp4Decisions.Count 3 'MP4 decision record count changed.'
Assert-Equal $mp4Decisions[0].action 'drop' 'MP4 should drop non-selected commentary audio.'
Assert-Equal $mp4Decisions[0].reason 'mp4_single_eac3_compatibility' 'MP4 drop reason should be explicit.'
Assert-Equal $mp4Decisions[1].action 'transcode' 'MP4 should transcode selected PCM audio to EAC3.'
Assert-True $mp4Decisions[1].is_default 'MP4 selected audio should be default.'
Assert-Equal $mp4Decisions[2].action 'drop' 'MP4 should drop non-selected alternate audio.'
$script:OutputContainer = 'mkv'

$script:AudioTranscodeAutoBitrateByChannels = $true
$scaledAudioArgs = @(Build-AudioArgs 'source.mkv')
$scaledBitrateIndex = [array]::IndexOf($scaledAudioArgs, '-b:a:1')
Assert-True ($scaledBitrateIndex -ge 0) 'Auto bitrate args did not include the transcoded PCM track bitrate option.'
Assert-Equal $scaledAudioArgs[$scaledBitrateIndex + 1] '192k' 'Auto bitrate by channels should scale stereo EAC3 transcode bitrate.'
$scaledDecisions = @(Get-LastAudioDecisionRecords)
Assert-Equal $scaledDecisions[1].bitrate '192k' 'Auto bitrate decision record should capture the scaled stereo bitrate.'
$script:AudioTranscodeAutoBitrateByChannels = $false

$script:AudioOverride = [pscustomobject]@{ keep_languages = @('jpn'); title_override = 'Japanese PCM Override' }
$filteredArgs = @(Build-AudioArgs 'source.mkv')
Assert-SequenceEqual $filteredArgs @(
    '-map','0:a:1',
    '-c:a:0','eac3',
    '-b:a:0','640k',
    '-ac:0','2',
    '-channel_layout:a:0','stereo',
    '-metadata:s:a:0','language=jpn',
    '-metadata:s:a:0','title=Japanese PCM Override',
    '-disposition:a:0','forced',
    '-disposition:a:0','default+forced'
) 'File-override audio filtering changed FFmpeg arguments.'
$filteredDecisions = @(Get-LastAudioDecisionRecords)
Assert-Equal $filteredDecisions.Count 3 'Filtered decision record count changed.'
Assert-Equal $filteredDecisions[0].action 'drop' 'First dropped audio decision changed.'
Assert-True (-not $filteredDecisions[0].is_default) 'Dropped audio track was incorrectly recorded as default.'
Assert-Equal $filteredDecisions[1].audio_ordinal 0 'Kept audio output ordinal changed.'
Assert-Equal $filteredDecisions[1].title 'Japanese PCM Override' 'Audio title override changed.'
Assert-Equal $filteredDecisions[2].action 'drop' 'Last dropped audio decision changed.'
Assert-True (-not $filteredDecisions[2].is_default) 'Dropped audio track was incorrectly recorded as default.'

$script:AudioOverride = $null
$script:ProbeMode = 'missing'
try {
    $null = @(Build-AudioArgs 'silent.mkv')
    throw 'Build-AudioArgs did not fail for no-audio input.'
} catch {
    if ([string]$_.Exception.Message -notmatch 'SOURCE_MEDIA_AUDIO_MISSING') {
        throw "Unexpected no-audio failure: $($_.Exception.Message)"
    }
}

$script:AllowNoAudio = $true
$noAudioArgs = @(Build-AudioArgs 'silent.mkv')
Assert-SequenceEqual $noAudioArgs @('-an') 'AllowNoAudio did not emit -an.'
$noAudioDecisions = @(Get-LastAudioDecisionRecords)
Assert-Equal $noAudioDecisions.Count 1 'AllowNoAudio decision record count changed.'
Assert-Equal $noAudioDecisions[0].action 'omit_all' 'AllowNoAudio decision action changed.'
Assert-Equal $noAudioDecisions[0].planned_action 'not_applicable' 'AllowNoAudio should expose explicit not-applicable evidence.'

foreach ($presenceProbeMode in @('presence-nonzero', 'presence-timedout', 'presence-stopped')) {
    foreach ($allowNoAudioValue in @($false, $true)) {
        $script:AllowNoAudio = $allowNoAudioValue
        $script:ProbeMode = $presenceProbeMode
        try {
            $null = @(Build-AudioArgs "$presenceProbeMode.mkv")
            throw "Build-AudioArgs did not fail for $presenceProbeMode with AllowNoAudio=$allowNoAudioValue."
        } catch {
            if ([string]$_.Exception.Message -notmatch 'SOURCE_MEDIA_AUDIO_PRESENCE_PROBE_FAILED') {
                throw "Unexpected audio presence-probe failure for $presenceProbeMode with AllowNoAudio=$allowNoAudioValue`: $($_.Exception.Message)"
            }
        }
    }
}

$script:AllowNoAudio = $false
$script:ProbeMode = 'metadata-failed'
try {
    $null = @(Build-AudioArgs 'metadata-failed.mkv')
    throw 'Build-AudioArgs did not fail when audio metadata probe failed.'
} catch {
    if ([string]$_.Exception.Message -notmatch 'SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED') {
        throw "Unexpected metadata-probe failure: $($_.Exception.Message)"
    }
}

Write-Host 'Audio policy checks passed.'
