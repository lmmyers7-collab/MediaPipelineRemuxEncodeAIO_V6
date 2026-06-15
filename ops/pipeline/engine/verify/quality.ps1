# ==============================================================================
# ops\pipeline\engine\verify\quality.ps1
# ==============================================================================
# Objective encode-quality verification helpers. The check compares the temporary
# encoded output against the scratch source and records diagnostic evidence before
# publish. Tool/probe failures fail open; configured quality floors can park an
# encode for operator review before publish.
# ==============================================================================

function Get-MediaQualityObjectValue {
    param(
        $Object,
        [Parameter(Mandatory)] [string] $Name,
        $Default = $null
    )

    if ($null -eq $Object) { return $Default }
    if ($Object -is [System.Collections.IDictionary]) {
        if ($Object.Contains($Name)) { return $Object[$Name] }
        return $Default
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($property) { return $property.Value }
    return $Default
}

function Set-MediaQualityObjectValue {
    param(
        [Parameter(Mandatory)] $Object,
        [Parameter(Mandatory)] [string] $Name,
        $Value
    )

    if ($Object -is [System.Collections.IDictionary]) {
        $Object[$Name] = $Value
        return
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($property) {
        $property.Value = $Value
    } else {
        Add-Member -InputObject $Object -NotePropertyName $Name -NotePropertyValue $Value -Force
    }
}

function ConvertTo-MediaQualityDouble {
    param(
        $Value,
        [double] $Default = 0.0
    )

    if ($null -eq $Value) { return $Default }
    $text = ([string]$Value).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) { return $Default }
    $parsed = 0.0
    if ([double]::TryParse(
        $text,
        [System.Globalization.NumberStyles]::Float,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [ref]$parsed
    )) {
        return $parsed
    }
    return $Default
}

function ConvertTo-MediaQualityInvariantString {
    param([double] $Value)
    return $Value.ToString('0.###', [System.Globalization.CultureInfo]::InvariantCulture)
}

function New-MediaQualityVerificationRecord {
    param(
        [string] $Metric = 'vmaf',
        [string] $SampleMode = 'sampled',
        [int] $SampleSeconds = 10,
        [int] $SampleCount = 3,
        [string] $ReferencePath = '',
        [string] $DistortedPath = '',
        [double] $DurationSeconds = 0.0,
        [string] $AlignedScale = '',
        [string] $AlignedFps = '',
        [string] $PixelFormat = '',
        $Score = $null,
        $MinWindowScore = $null,
        [array] $WindowScores = @(),
        [array] $WindowStarts = @(),
        [string] $ToolError = '',
        [string] $Outcome = ''
    )

    return [ordered]@{
        schema                    = 'quality_verification.v1'
        diagnostic_only           = $false
        enabled                   = $true
        attempted                 = $true
        metric                    = ([string]$Metric).Trim().ToLowerInvariant()
        score                     = $Score
        min_window_score          = $MinWindowScore
        window_scores             = @($WindowScores)
        window_starts             = @($WindowStarts)
        sample_mode               = ([string]$SampleMode).Trim().ToLowerInvariant()
        sample_seconds            = [int]$SampleSeconds
        sample_count              = [int]$SampleCount
        reference_path            = [string]$ReferencePath
        distorted_path            = [string]$DistortedPath
        aligned_scale             = [string]$AlignedScale
        aligned_fps               = [string]$AlignedFps
        pixel_format              = [string]$PixelFormat
        duration_seconds          = [math]::Round([double]$DurationSeconds, 3)
        tool_error                = [string]$ToolError
        outcome                   = [string]$Outcome
        warn_threshold            = $null
        fail_threshold            = $null
        fail_action               = ''
        below_warn_threshold      = $false
        below_fail_threshold      = $false
        block_publish             = $false
    }
}

function Get-MediaQualityStreamInfo {
    param(
        [Parameter(Mandatory)] [string] $FilePath,
        [int] $TimeoutSeconds = 30
    )

    try {
        $result = Invoke-FFprobeCommand -ArgumentList @(
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,avg_frame_rate,pix_fmt,duration:format=duration',
            '-of', 'json',
            '-i', $FilePath
        ) -TimeoutSeconds $TimeoutSeconds -Stage 'quality-probe'

        $exitCode = [int](Get-MediaQualityObjectValue -Object $result -Name 'ExitCode' -Default -1)
        $stderr = [string](Get-MediaQualityObjectValue -Object $result -Name 'Stderr' -Default (Get-MediaQualityObjectValue -Object $result -Name 'Error' -Default ''))
        if ($exitCode -ne 0 -or [bool](Get-MediaQualityObjectValue -Object $result -Name 'TimedOut' -Default $false) -or [bool](Get-MediaQualityObjectValue -Object $result -Name 'Stopped' -Default $false)) {
            if ([string]::IsNullOrWhiteSpace($stderr)) { $stderr = "ffprobe exited with code $exitCode" }
            return [pscustomobject][ordered]@{ Ok = $false; Width = 0; Height = 0; FrameRate = ''; PixFmt = ''; DurationSeconds = 0.0; Error = $stderr }
        }

        $jsonText = [string](Get-MediaQualityObjectValue -Object $result -Name 'Stdout' -Default (Get-MediaQualityObjectValue -Object $result -Name 'Output' -Default ''))
        if ([string]::IsNullOrWhiteSpace($jsonText)) {
            return [pscustomobject][ordered]@{ Ok = $false; Width = 0; Height = 0; FrameRate = ''; PixFmt = ''; DurationSeconds = 0.0; Error = 'ffprobe returned no JSON' }
        }

        $json = $jsonText | ConvertFrom-Json
        $stream = @($json.streams)[0]
        if ($null -eq $stream) {
            return [pscustomobject][ordered]@{ Ok = $false; Width = 0; Height = 0; FrameRate = ''; PixFmt = ''; DurationSeconds = 0.0; Error = 'ffprobe found no video stream' }
        }

        $duration = ConvertTo-MediaQualityDouble -Value $stream.duration -Default 0.0
        if ($duration -le 0.0 -and $json.format) {
            $duration = ConvertTo-MediaQualityDouble -Value $json.format.duration -Default 0.0
        }
        $width = [int](ConvertTo-MediaQualityDouble -Value $stream.width -Default 0.0)
        $height = [int](ConvertTo-MediaQualityDouble -Value $stream.height -Default 0.0)
        $frameRate = ([string]$stream.avg_frame_rate).Trim()
        if ($width -le 0 -or $height -le 0) {
            return [pscustomobject][ordered]@{ Ok = $false; Width = $width; Height = $height; FrameRate = $frameRate; PixFmt = [string]$stream.pix_fmt; DurationSeconds = $duration; Error = 'ffprobe video dimensions were missing' }
        }

        return [pscustomobject][ordered]@{
            Ok              = $true
            Width           = $width
            Height          = $height
            FrameRate       = $frameRate
            PixFmt          = [string]$stream.pix_fmt
            DurationSeconds = [math]::Round($duration, 3)
            Error           = ''
        }
    } catch {
        return [pscustomobject][ordered]@{ Ok = $false; Width = 0; Height = 0; FrameRate = ''; PixFmt = ''; DurationSeconds = 0.0; Error = [string]$_ }
    }
}

function Get-MediaQualitySampleWindows {
    param(
        [double] $DurationSeconds,
        [int] $SampleSeconds,
        [int] $SampleCount
    )

    $sampleSecondsValue = [math]::Max(1.0, [double]$SampleSeconds)
    $sampleCountValue = [math]::Max(1, [int]$SampleCount)
    if ($DurationSeconds -le 0.0) { return $null }
    if ($DurationSeconds -le (2.0 * $sampleSecondsValue * $sampleCountValue)) { return $null }

    $spanStart = 0.05 * $DurationSeconds
    $spanEnd = (0.95 * $DurationSeconds) - $sampleSecondsValue
    if ($spanEnd -le $spanStart) { return $null }

    $starts = New-Object System.Collections.Generic.List[double]
    if ($sampleCountValue -eq 1) {
        [void]$starts.Add([math]::Round((($spanStart + $spanEnd) / 2.0), 3))
        return @($starts)
    }

    $step = ($spanEnd - $spanStart) / [double]($sampleCountValue - 1)
    for ($index = 0; $index -lt $sampleCountValue; $index++) {
        [void]$starts.Add([math]::Round(($spanStart + ($step * $index)), 3))
    }
    return @($starts)
}

function ConvertTo-MediaQualityFilterPath {
    param([Parameter(Mandatory)] [string] $Path)

    $normalized = $Path.Replace('\', '/')
    return ($normalized -replace '^([A-Za-z]):', '$1\\:')
}

function New-MediaQualityFilterGraph {
    param(
        [Parameter(Mandatory)] [string] $Metric,
        [Parameter(Mandatory)] $RefInfo,
        [string] $LogPath = ''
    )

    $metricText = ([string]$Metric).Trim().ToLowerInvariant()
    $width = [int](Get-MediaQualityObjectValue -Object $RefInfo -Name 'Width' -Default 0)
    $height = [int](Get-MediaQualityObjectValue -Object $RefInfo -Name 'Height' -Default 0)
    $frameRate = ([string](Get-MediaQualityObjectValue -Object $RefInfo -Name 'FrameRate' -Default '')).Trim()
    $pixFmt = ([string](Get-MediaQualityObjectValue -Object $RefInfo -Name 'PixFmt' -Default '')).Trim().ToLowerInvariant()
    $targetPixFmt = if ($pixFmt -match '10|12') { 'yuv420p10le' } else { 'yuv420p' }
    $distorted = "[0:v]setpts=PTS-STARTPTS,fps=fps=$frameRate,scale=${width}:${height}:flags=bicubic,format=$targetPixFmt[dist]"
    $reference = "[1:v]setpts=PTS-STARTPTS,fps=fps=$frameRate,format=$targetPixFmt[ref]"

    $tail = switch ($metricText) {
        'ssim' { '[dist][ref]ssim' }
        'psnr' { '[dist][ref]psnr' }
        default {
            $threads = [math]::Min(8, [math]::Max(1, [int][Environment]::ProcessorCount))
            $escapedLogPath = ConvertTo-MediaQualityFilterPath -Path $LogPath
            "[dist][ref]libvmaf=log_fmt=json:log_path=${escapedLogPath}:n_threads=$threads"
        }
    }
    return "$distorted;$reference;$tail"
}

function ConvertFrom-MediaQualityToolOutput {
    param(
        [Parameter(Mandatory)] [string] $Metric,
        [string] $LogJsonPath = '',
        [string] $StdErrText = ''
    )

    $metricText = ([string]$Metric).Trim().ToLowerInvariant()
    try {
        switch ($metricText) {
            'ssim' {
                $matches = [regex]::Matches([string]$StdErrText, 'All:([0-9.]+)')
                if ($matches.Count -le 0) {
                    return [pscustomobject][ordered]@{ Ok = $false; Score = $null; Error = 'SSIM score not found in ffmpeg stderr' }
                }
                $score = ConvertTo-MediaQualityDouble -Value $matches[$matches.Count - 1].Groups[1].Value -Default -1.0
                if ($score -lt 0.0) {
                    return [pscustomobject][ordered]@{ Ok = $false; Score = $null; Error = 'SSIM score could not be parsed' }
                }
                return [pscustomobject][ordered]@{ Ok = $true; Score = [math]::Round($score, 6); Error = '' }
            }
            'psnr' {
                $matches = [regex]::Matches([string]$StdErrText, 'average:([0-9.]+|inf)')
                if ($matches.Count -le 0) {
                    return [pscustomobject][ordered]@{ Ok = $false; Score = $null; Error = 'PSNR score not found in ffmpeg stderr' }
                }
                $scoreText = $matches[$matches.Count - 1].Groups[1].Value
                $score = if ($scoreText -eq 'inf') { 100.0 } else { ConvertTo-MediaQualityDouble -Value $scoreText -Default -1.0 }
                if ($score -lt 0.0) {
                    return [pscustomobject][ordered]@{ Ok = $false; Score = $null; Error = 'PSNR score could not be parsed' }
                }
                return [pscustomobject][ordered]@{ Ok = $true; Score = [math]::Round($score, 3); Error = '' }
            }
            default {
                if ([string]::IsNullOrWhiteSpace($LogJsonPath) -or -not (Test-Path -LiteralPath $LogJsonPath)) {
                    return [pscustomobject][ordered]@{ Ok = $false; Score = $null; Error = 'VMAF JSON log was not written' }
                }
                $json = Get-Content -LiteralPath $LogJsonPath -Raw | ConvertFrom-Json
                $pooled = Get-MediaQualityObjectValue -Object $json -Name 'pooled_metrics' -Default $null
                $vmaf = Get-MediaQualityObjectValue -Object $pooled -Name 'vmaf' -Default $null
                $mean = Get-MediaQualityObjectValue -Object $vmaf -Name 'mean' -Default $null
                if ($null -eq $mean) {
                    return [pscustomobject][ordered]@{ Ok = $false; Score = $null; Error = 'VMAF mean score missing from JSON log' }
                }
                return [pscustomobject][ordered]@{ Ok = $true; Score = [math]::Round((ConvertTo-MediaQualityDouble -Value $mean -Default -1.0), 3); Error = '' }
            }
        }
    } catch {
        return [pscustomobject][ordered]@{ Ok = $false; Score = $null; Error = [string]$_ }
    }
}

function Resolve-MediaQualityLogDirectory {
    $configured = $null
    $processingDirVariable = Get-Variable -Name 'processingDir' -Scope Script -ErrorAction SilentlyContinue
    if ($processingDirVariable -and -not [string]::IsNullOrWhiteSpace([string]$processingDirVariable.Value)) {
        $configured = [string]$processingDirVariable.Value
    }
    if ([string]::IsNullOrWhiteSpace($configured)) { $configured = [System.IO.Path]::GetTempPath() }
    [System.IO.Directory]::CreateDirectory($configured) | Out-Null
    return $configured
}

function Invoke-MediaQualityVerification {
    param(
        [Parameter(Mandatory)] [string] $ReferencePath,
        [Parameter(Mandatory)] [string] $DistortedPath,
        [string] $Metric = 'vmaf',
        [string] $SampleMode = 'sampled',
        [int] $SampleSeconds = 10,
        [int] $SampleCount = 3,
        [int] $TimeoutSeconds = 1800
    )

    $metricText = ([string]$Metric).Trim().ToLowerInvariant()
    if ($metricText -notin @('vmaf', 'ssim', 'psnr')) { $metricText = 'vmaf' }
    $sampleModeText = ([string]$SampleMode).Trim().ToLowerInvariant()
    if ($sampleModeText -notin @('sampled', 'full')) { $sampleModeText = 'sampled' }
    $sampleSecondsValue = [math]::Max(1, [int]$SampleSeconds)
    $sampleCountValue = [math]::Max(1, [int]$SampleCount)
    $timeoutValue = [math]::Max(1, [int]$TimeoutSeconds)

    $probeTimeout = 30
    $probeTimeoutVariable = Get-Variable -Name 'OutputValidationProbeTimeoutSeconds' -Scope Script -ErrorAction SilentlyContinue
    if ($probeTimeoutVariable -and [int]$probeTimeoutVariable.Value -gt 0) {
        $probeTimeout = [int]$probeTimeoutVariable.Value
    }

    $referenceInfo = Get-MediaQualityStreamInfo -FilePath $ReferencePath -TimeoutSeconds $probeTimeout
    if (-not [bool]$referenceInfo.Ok) {
        return New-MediaQualityVerificationRecord -Metric $metricText -SampleMode $sampleModeText -SampleSeconds $sampleSecondsValue -SampleCount $sampleCountValue -ReferencePath $ReferencePath -DistortedPath $DistortedPath -ToolError ("reference probe failed: {0}" -f [string]$referenceInfo.Error) -Outcome 'error'
    }
    $distortedInfo = Get-MediaQualityStreamInfo -FilePath $DistortedPath -TimeoutSeconds $probeTimeout
    if (-not [bool]$distortedInfo.Ok) {
        return New-MediaQualityVerificationRecord -Metric $metricText -SampleMode $sampleModeText -SampleSeconds $sampleSecondsValue -SampleCount $sampleCountValue -ReferencePath $ReferencePath -DistortedPath $DistortedPath -ToolError ("distorted probe failed: {0}" -f [string]$distortedInfo.Error) -Outcome 'error'
    }
    if ([double]$referenceInfo.DurationSeconds -le 0.0) {
        return New-MediaQualityVerificationRecord -Metric $metricText -SampleMode $sampleModeText -SampleSeconds $sampleSecondsValue -SampleCount $sampleCountValue -ReferencePath $ReferencePath -DistortedPath $DistortedPath -ToolError 'reference duration was missing' -Outcome 'error'
    }
    if ([string]::IsNullOrWhiteSpace([string]$referenceInfo.FrameRate) -or [string]$referenceInfo.FrameRate -eq '0/0') {
        return New-MediaQualityVerificationRecord -Metric $metricText -SampleMode $sampleModeText -SampleSeconds $sampleSecondsValue -SampleCount $sampleCountValue -ReferencePath $ReferencePath -DistortedPath $DistortedPath -DurationSeconds ([double]$referenceInfo.DurationSeconds) -ToolError 'reference frame rate was missing' -Outcome 'error'
    }

    $effectiveMode = 'full'
    $windowStarts = @()
    if ($sampleModeText -eq 'sampled') {
        $windows = Get-MediaQualitySampleWindows -DurationSeconds ([double]$referenceInfo.DurationSeconds) -SampleSeconds $sampleSecondsValue -SampleCount $sampleCountValue
        if ($null -ne $windows) {
            $windowStarts = @($windows)
            $effectiveMode = 'sampled'
        }
    }

    $logDirectory = Resolve-MediaQualityLogDirectory
    $temporaryLogs = New-Object System.Collections.Generic.List[string]
    $scores = New-Object System.Collections.Generic.List[double]
    try {
        $runStarts = New-Object System.Collections.Generic.List[object]
        if ($effectiveMode -eq 'sampled') {
            foreach ($start in @($windowStarts)) { [void]$runStarts.Add($start) }
        } else {
            [void]$runStarts.Add($null)
        }
        foreach ($windowStart in $runStarts) {
            $logPath = Join-Path $logDirectory ("quality-{0}-{1}.json" -f $metricText, ([guid]::NewGuid().ToString('N')))
            [void]$temporaryLogs.Add($logPath)
            $filterGraph = New-MediaQualityFilterGraph -Metric $metricText -RefInfo $referenceInfo -LogPath $logPath

            $ffmpegArgs = New-Object System.Collections.Generic.List[string]
            foreach ($arg in @('-hide_banner', '-nostats', '-y')) { [void]$ffmpegArgs.Add($arg) }
            if ($null -ne $windowStart) {
                [void]$ffmpegArgs.Add('-ss')
                [void]$ffmpegArgs.Add((ConvertTo-MediaQualityInvariantString -Value ([double]$windowStart)))
                [void]$ffmpegArgs.Add('-t')
                [void]$ffmpegArgs.Add((ConvertTo-MediaQualityInvariantString -Value ([double]$sampleSecondsValue)))
            }
            [void]$ffmpegArgs.Add('-i')
            [void]$ffmpegArgs.Add($DistortedPath)
            if ($null -ne $windowStart) {
                [void]$ffmpegArgs.Add('-ss')
                [void]$ffmpegArgs.Add((ConvertTo-MediaQualityInvariantString -Value ([double]$windowStart)))
                [void]$ffmpegArgs.Add('-t')
                [void]$ffmpegArgs.Add((ConvertTo-MediaQualityInvariantString -Value ([double]$sampleSecondsValue)))
            }
            [void]$ffmpegArgs.Add('-i')
            [void]$ffmpegArgs.Add($ReferencePath)
            [void]$ffmpegArgs.Add('-lavfi')
            [void]$ffmpegArgs.Add($filterGraph)
            [void]$ffmpegArgs.Add('-f')
            [void]$ffmpegArgs.Add('null')
            [void]$ffmpegArgs.Add('-')

            $result = Invoke-FFmpegCommand -ArgumentList @($ffmpegArgs) -TimeoutSeconds $timeoutValue -Stage 'encode-quality-verify' -ProcessPriority 'BelowNormal'
            $exitCode = [int](Get-MediaQualityObjectValue -Object $result -Name 'ExitCode' -Default -1)
            $stderr = [string](Get-MediaQualityObjectValue -Object $result -Name 'Stderr' -Default (Get-MediaQualityObjectValue -Object $result -Name 'Error' -Default ''))
            if ([bool](Get-MediaQualityObjectValue -Object $result -Name 'Stopped' -Default $false)) {
                return New-MediaQualityVerificationRecord -Metric $metricText -SampleMode $effectiveMode -SampleSeconds $sampleSecondsValue -SampleCount $sampleCountValue -ReferencePath $ReferencePath -DistortedPath $DistortedPath -DurationSeconds ([double]$referenceInfo.DurationSeconds) -AlignedScale ("{0}x{1}" -f $referenceInfo.Width, $referenceInfo.Height) -AlignedFps $referenceInfo.FrameRate -PixelFormat $referenceInfo.PixFmt -ToolError ($stderr.Trim()) -Outcome 'stopped'
            }
            if ([bool](Get-MediaQualityObjectValue -Object $result -Name 'TimedOut' -Default $false) -or $exitCode -ne 0) {
                if ([string]::IsNullOrWhiteSpace($stderr)) { $stderr = "ffmpeg exited with code $exitCode" }
                return New-MediaQualityVerificationRecord -Metric $metricText -SampleMode $effectiveMode -SampleSeconds $sampleSecondsValue -SampleCount $sampleCountValue -ReferencePath $ReferencePath -DistortedPath $DistortedPath -DurationSeconds ([double]$referenceInfo.DurationSeconds) -AlignedScale ("{0}x{1}" -f $referenceInfo.Width, $referenceInfo.Height) -AlignedFps $referenceInfo.FrameRate -PixelFormat $referenceInfo.PixFmt -ToolError ($stderr.Trim()) -Outcome 'error'
            }

            $parsed = ConvertFrom-MediaQualityToolOutput -Metric $metricText -LogJsonPath $logPath -StdErrText $stderr
            if (-not [bool]$parsed.Ok) {
                return New-MediaQualityVerificationRecord -Metric $metricText -SampleMode $effectiveMode -SampleSeconds $sampleSecondsValue -SampleCount $sampleCountValue -ReferencePath $ReferencePath -DistortedPath $DistortedPath -DurationSeconds ([double]$referenceInfo.DurationSeconds) -AlignedScale ("{0}x{1}" -f $referenceInfo.Width, $referenceInfo.Height) -AlignedFps $referenceInfo.FrameRate -PixelFormat $referenceInfo.PixFmt -ToolError ([string]$parsed.Error) -Outcome 'error'
            }
            [void]$scores.Add([double]$parsed.Score)
        }
    } finally {
        foreach ($logPath in @($temporaryLogs)) {
            if (-not [string]::IsNullOrWhiteSpace($logPath)) {
                Remove-Item -LiteralPath $logPath -Force -ErrorAction SilentlyContinue
            }
        }
    }

    if ($scores.Count -le 0) {
        return New-MediaQualityVerificationRecord -Metric $metricText -SampleMode $effectiveMode -SampleSeconds $sampleSecondsValue -SampleCount $sampleCountValue -ReferencePath $ReferencePath -DistortedPath $DistortedPath -DurationSeconds ([double]$referenceInfo.DurationSeconds) -AlignedScale ("{0}x{1}" -f $referenceInfo.Width, $referenceInfo.Height) -AlignedFps $referenceInfo.FrameRate -PixelFormat $referenceInfo.PixFmt -ToolError 'no quality scores were produced' -Outcome 'error'
    }

    $sum = 0.0
    $minScore = [double]::PositiveInfinity
    $roundedScores = New-Object System.Collections.Generic.List[double]
    foreach ($score in @($scores)) {
        $sum += [double]$score
        if ([double]$score -lt $minScore) { $minScore = [double]$score }
        [void]$roundedScores.Add([math]::Round([double]$score, 3))
    }
    $meanScore = [math]::Round(($sum / [double]$scores.Count), 3)
    $windowStartEvidence = if ($effectiveMode -eq 'sampled') { @($windowStarts | ForEach-Object { [math]::Round([double]$_, 3) }) } else { @() }

    return New-MediaQualityVerificationRecord `
        -Metric $metricText `
        -SampleMode $effectiveMode `
        -SampleSeconds $sampleSecondsValue `
        -SampleCount $sampleCountValue `
        -ReferencePath $ReferencePath `
        -DistortedPath $DistortedPath `
        -DurationSeconds ([double]$referenceInfo.DurationSeconds) `
        -AlignedScale ("{0}x{1}" -f $referenceInfo.Width, $referenceInfo.Height) `
        -AlignedFps $referenceInfo.FrameRate `
        -PixelFormat $referenceInfo.PixFmt `
        -Score $meanScore `
        -MinWindowScore ([math]::Round($minScore, 3)) `
        -WindowScores @($roundedScores) `
        -WindowStarts @($windowStartEvidence)
}

function Resolve-MediaQualityOutcome {
    param(
        [Parameter(Mandatory)] $Record,
        [double] $WarnThreshold = 90.0,
        [double] $FailThreshold = 75.0,
        [string] $FailAction = 'warn_only'
    )

    $failActionText = ([string]$FailAction).Trim().ToLowerInvariant()
    if ($failActionText -notin @('warn_only', 'block_review')) { $failActionText = 'warn_only' }
    $score = Get-MediaQualityObjectValue -Object $Record -Name 'score' -Default $null
    $toolError = [string](Get-MediaQualityObjectValue -Object $Record -Name 'tool_error' -Default '')
    $currentOutcome = [string](Get-MediaQualityObjectValue -Object $Record -Name 'outcome' -Default '')
    $hasScore = ($null -ne $score)
    $scoreValue = if ($hasScore) { [double]$score } else { 0.0 }
    $belowFail = ($hasScore -and $FailThreshold -gt 0.0 -and $scoreValue -lt $FailThreshold)
    $belowWarn = ($hasScore -and $WarnThreshold -gt 0.0 -and $scoreValue -lt $WarnThreshold)
    $block = $false
    $outcome = 'pass'

    if (-not [string]::IsNullOrWhiteSpace($toolError) -or -not $hasScore) {
        $outcome = if ($currentOutcome -eq 'stopped') { 'stopped' } else { 'error' }
    } elseif ($belowFail) {
        $outcome = 'fail'
        $block = ($failActionText -eq 'block_review')
    } elseif ($belowWarn) {
        $outcome = 'warn'
    }

    Set-MediaQualityObjectValue -Object $Record -Name 'outcome' -Value $outcome
    Set-MediaQualityObjectValue -Object $Record -Name 'warn_threshold' -Value ([math]::Round([double]$WarnThreshold, 3))
    Set-MediaQualityObjectValue -Object $Record -Name 'fail_threshold' -Value ([math]::Round([double]$FailThreshold, 3))
    Set-MediaQualityObjectValue -Object $Record -Name 'fail_action' -Value $failActionText
    Set-MediaQualityObjectValue -Object $Record -Name 'below_warn_threshold' -Value ([bool]$belowWarn)
    Set-MediaQualityObjectValue -Object $Record -Name 'below_fail_threshold' -Value ([bool]$belowFail)
    Set-MediaQualityObjectValue -Object $Record -Name 'block_publish' -Value ([bool]$block)
    return $Record
}
