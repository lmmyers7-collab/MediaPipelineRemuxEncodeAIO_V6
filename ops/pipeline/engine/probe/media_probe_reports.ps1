# Extracted from ops/pipeline/engine/probe/media_probe.ps1. Responsibility: duration and compatibility report rendering

function Get-MediaDuration {
    param([string]$FilePath)
    if (-not (Test-Path -LiteralPath $FilePath)) { return 0.0 }
    $r = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1","--",$FilePath
    ) -TimeoutSeconds 30 -Stage 'media-duration'
    if ($r.ExitCode -ne 0) { return 0.0 }
    $d = 0.0
    if ([double]::TryParse($r.Output.Trim(), [ref]$d)) { return $d }
    return 0.0
}

function Get-PrimaryAVEndTime {
    param(
        [string]$FilePath,
        [int]$TimeoutSeconds = 180
    )

    if (-not (Test-Path -LiteralPath $FilePath)) { return 0.0 }

    $maxEnd = 0.0
    $found  = $false
    foreach ($selector in @('v:0', 'a:0')) {
        $probe = Invoke-FFprobeCommand -ArgumentList @(
            '-v', 'error',
            '-select_streams', $selector,
            '-show_entries', 'packet=pts_time',
            '-of', 'csv=p=0',
            '--', $FilePath
        ) -TimeoutSeconds $TimeoutSeconds -Stage 'primary-av-end-time'

        if ($probe.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($probe.Output)) {
            continue
        }

        $lines = $probe.Output -split '\r?\n' | Where-Object { $_ -match '\S' }
        if (-not $lines -or $lines.Count -eq 0) {
            continue
        }

        $lastLine = $lines[-1].Trim()
        $match = [regex]::Match($lastLine, '[-+]?\d+(?:\.\d+)?')
        if (-not $match.Success) {
            continue
        }

        try {
            $end = [double]::Parse($match.Value, [System.Globalization.CultureInfo]::InvariantCulture)
            if ($end -gt $maxEnd) { $maxEnd = $end }
            $found = $true
        } catch {}
    }

    if ($found) { return $maxEnd }
    return 0.0
}

function Test-DurationMatch {
    param(
        [string]$SourcePath,
        [string]$OutputPath,
        [double]$ToleranceSeconds = 1.0,
        [string]$Label = "ENCODE",
        [switch]$AllowAVFallback
    )
    $srcDur = Get-MediaDuration $SourcePath
    $outDur = Get-MediaDuration $OutputPath
    if ($srcDur -le 0) {
        Write-Log "${Label}: source duration probe failed - treating verification as failed" "ERROR"
        return $false
    }
    if ($outDur -le 0) {
        Write-Log "${Label}: output duration probe failed - treating as corrupt" "ERROR"
        return $false
    }
    $delta = [math]::Abs($srcDur - $outDur)
    if ($delta -gt $ToleranceSeconds) {
        if ($AllowAVFallback) {
            $srcAvEnd = Get-PrimaryAVEndTime -FilePath $SourcePath
            $outAvEnd = Get-PrimaryAVEndTime -FilePath $OutputPath

            if ($srcAvEnd -gt 0 -and $outAvEnd -gt 0) {
                $avDelta = [math]::Abs($srcAvEnd - $outAvEnd)
                if ($avDelta -le $ToleranceSeconds) {
                    $durationMessage = ("{0}: container duration mismatch accepted because primary A/V end times match " +
                        "(source container {1:N2}s, output container {2:N2}s, source A/V {3:N2}s, output A/V {4:N2}s, A/V delta {5:N2}s)") -f $Label, $srcDur, $outDur, $srcAvEnd, $outAvEnd, $avDelta
                    Write-Log $durationMessage "WARN"
                    return $true
                }

                $durationMessage = ("{0}: DURATION MISMATCH - source container {1:N2}s, output container {2:N2}s, delta {3:N2}s " +
                    "(tolerance {4}s); primary A/V end times also differ (source A/V {5:N2}s, output A/V {6:N2}s, A/V delta {7:N2}s)") -f $Label, $srcDur, $outDur, $delta, $ToleranceSeconds, $srcAvEnd, $outAvEnd, $avDelta
                Write-Log $durationMessage "ERROR"
                return $false
            }

            $durationMessage = ("{0}: DURATION MISMATCH - source {1:N2}s, output {2:N2}s, delta {3:N2}s (tolerance {4}s); " +
                "primary A/V fallback probe failed") -f $Label, $srcDur, $outDur, $delta, $ToleranceSeconds
            Write-Log $durationMessage "ERROR"
            return $false
        }

        $durationMessage = ("{0}: DURATION MISMATCH - source {1:N2}s, output {2:N2}s, delta {3:N2}s (tolerance {4}s)") -f $Label, $srcDur, $outDur, $delta, $ToleranceSeconds
        Write-Log $durationMessage "ERROR"
        return $false
    }
    $durationMessage = ("{0}: duration verified (source {1:N2}s, output {2:N2}s, delta {3:N2}s)") -f $Label, $srcDur, $outDur, $delta
    Write-Log $durationMessage "DEBUG"
    return $true
}

function Write-OutputSummary {
    param([string]$FilePath, [string]$Route)
    if (-not (Test-Path -LiteralPath $FilePath)) { return }
    $r = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error",
        "-show_entries","stream=index,codec_type,codec_name,width,height,channels,disposition:stream_tags=language,title",
        "-of","json","--",$FilePath
    ) -TimeoutSeconds 30 -Stage 'output-summary-probe'
    if ($r.ExitCode -ne 0) { return }

    try {
        $json    = $r.Output | ConvertFrom-Json
        $sizeGB  = (Get-Item -LiteralPath $FilePath).Length / 1GB
        $parts   = [System.Collections.Generic.List[string]]::new()
        $parts.Add(("{0:N2}GB" -f $sizeGB))

        $vid     = $json.streams | Where-Object { $_.codec_type -eq 'video' } | Select-Object -First 1
        if ($vid) {
            $res  = if ($vid.height -ge 2000) { '4K' } elseif ($vid.height -ge 1000) { '1080p' } elseif ($vid.height -ge 700) { '720p' } else { "$($vid.height)p" }
            $parts.Add(("{0} {1}" -f $vid.codec_name.ToUpper(), $res))
        }

        $auds = @($json.streams | Where-Object { $_.codec_type -eq 'audio' })
        if ($auds.Count -gt 0) {
            $aParts = foreach ($a in $auds) {
                $lang = if ($a.tags.language) { $a.tags.language.ToUpper() } else { 'UND' }
                $ch   = if ($a.channels) { $a.channels } else { '?' }
                $layout = switch ([int]$ch) {
                    1 {'1.0'} 2 {'2.0'} 3 {'2.1'} 4 {'4.0'} 5 {'4.1'} 6 {'5.1'} 7 {'6.1'} 8 {'7.1'}
                    default { "${ch}ch" }
                }
                $def  = if ($a.disposition.default -eq 1) { ' [def]' } else { '' }
                "$lang $layout $($a.codec_name.ToUpper())$def"
            }
            $parts.Add(($aParts -join ', '))
        }

        $subs = @($json.streams | Where-Object { $_.codec_type -eq 'subtitle' })
        if ($subs.Count -gt 0) {
            $sParts = foreach ($s in $subs) {
                $lang = if ($s.tags.language) { $s.tags.language.ToUpper() } else { 'UND' }
                $subtitleCodec = if ($s.codec_name) { ([string]$s.codec_name).ToLowerInvariant() } else { '' }
                $codec = if ($subtitleCodec -in (Get-MediaSubtitleCodecSrtNames)) {
                    'SRT'
                } elseif ($subtitleCodec -in (Get-MediaSubtitleCodecAssNames)) {
                    'ASS'
                } else {
                    $subtitleCodec.ToUpperInvariant()
                }
                $flags = @()
                if ($s.disposition.default -eq 1) { $flags += 'def' }
                if ($s.disposition.forced  -eq 1) { $flags += 'forced' }
                $title = if ($s.tags.title) { $s.tags.title.ToLower() } else { '' }
                if ($title -match 'sign|song|karaoke') { $flags += 'signs' }
                $flagStr = if ($flags.Count) { ' [' + ($flags -join ',') + ']' } else { '' }
                "$lang $codec$flagStr"
            }
            $parts.Add(($sParts -join ', '))
        }

        $routeLabel = if ($Route -eq (Get-MediaRouteRemuxName)) {
            '(remux)'
        } elseif ($Route -eq (Get-MediaRouteEncodeName)) {
            '(encode)'
        } elseif ($Route -eq (Get-MediaRouteEncodeCpuFallbackName)) {
            '(encode, CPU)'
        } else {
            ''
        }
        Write-Log ("OUTPUT: " + ($parts -join ' | ') + " $routeLabel").Trim()
    } catch {
        Write-Log "Output summary failed for $FilePath : $_" "WARN"
    }
}

function Write-PlexCompatibilityReport {
    param(
        [string]$FilePath,
        [string]$Context = ''
    )

    $probe = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error",
        "-show_entries","stream=index,codec_name,codec_type,disposition:stream_tags=language,title",
        "-of","json","--",$FilePath
    ) -TimeoutSeconds 45 -Stage 'plex-compatibility-probe'
    if ($probe.ExitCode -ne 0) {
        Write-Log "${Context}PLEX CHECK: ffprobe failed for compatibility summary" "WARN"
        return
    }

    try {
        $json = $probe.Output | ConvertFrom-Json
    } catch {
        Write-Log "${Context}PLEX CHECK: could not parse ffprobe output" "WARN"
        return
    }

    if (-not $json.streams) {
        Write-Log "${Context}PLEX CHECK: no streams found in output" "WARN"
        return
    }

    $video = @($json.streams | Where-Object { $_.codec_type -eq 'video' } | Select-Object -First 1)[0]
    $audio = @($json.streams | Where-Object { $_.codec_type -eq 'audio' })
    $subs  = @($json.streams | Where-Object { $_.codec_type -eq 'subtitle' })

    $defaultAudio = @($audio | Where-Object { $_.disposition.default -eq 1 } | Select-Object -First 1)[0]
    if (-not $defaultAudio) { $defaultAudio = @($audio | Select-Object -First 1)[0] }
    $defaultSub = @($subs | Where-Object { $_.disposition.default -eq 1 } | Select-Object -First 1)[0]

    $videoCodec = if ($video -and $video.codec_name) { $video.codec_name.ToLower() } else { 'unknown' }
    $audioCodec = if ($defaultAudio -and $defaultAudio.codec_name) { $defaultAudio.codec_name.ToLower() } else { 'none' }
    $audioLang  = if ($defaultAudio -and $defaultAudio.tags.language) { $defaultAudio.tags.language.ToLower() } else { 'und' }
    $subCodec   = if ($defaultSub -and $defaultSub.codec_name) { $defaultSub.codec_name.ToLower() } else { 'none' }
    $subLang    = if ($defaultSub -and $defaultSub.tags.language) { $defaultSub.tags.language.ToLower() } else { 'none' }
    $hasTextSubs = @($subs | Where-Object { $_.codec_name -in (Get-MediaSubtitleCodecSrtNames) }).Count -gt 0

    $outlook = 'high'
    $notes = [System.Collections.Generic.List[string]]::new()

    if ($audioCodec -in (Get-MediaAudioCodecPlexTranscodeRiskNames)) {
        $outlook = 'mixed'
        $notes.Add("default audio codec '$audioCodec' may force Plex transcode on some clients")
    }
    if ($subCodec -in (Get-MediaSubtitleCodecAssNames)) {
        $outlook = 'mixed'
        $notes.Add("default subtitle codec '$subCodec' is less Plex-friendly than SRT")
    }
    if ($subCodec -in (Get-MediaSubtitleCodecBdpgsNames)) {
        $outlook = 'low'
        $notes.Add("default subtitle codec '$subCodec' usually forces image-based subtitle handling")
    }
    if ($subs.Count -gt 0 -and -not $hasTextSubs) {
        if ($outlook -eq 'high') { $outlook = 'mixed' }
        $notes.Add('no SRT text subtitle track present in the output')
    }
    if ($videoCodec -notin (Get-MediaVideoCodecPlexDirectPlayNames)) {
        if ($outlook -eq 'high') { $outlook = 'mixed' }
        $notes.Add("video codec '$videoCodec' may not direct play broadly")
    }

    Write-Log ("{0}PLEX CHECK: video={1} | default audio={2}/{3} | default subtitles={4}/{5} | outlook={6}" -f $Context, $videoCodec, $audioLang, $audioCodec, $subLang, $subCodec, $outlook.ToUpperInvariant())
    foreach ($note in $notes) {
        Write-Log "${Context}PLEX CHECK: $note" "WARN"
    }
}
