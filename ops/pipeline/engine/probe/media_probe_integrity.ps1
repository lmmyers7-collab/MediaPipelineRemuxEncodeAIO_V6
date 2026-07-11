# Extracted from ops/pipeline/engine/probe/media_probe.ps1. Responsibility: file integrity and stability checks

function New-FileIntegrityResult {
    param(
        [bool]$Ok,
        [string]$Reason,
        [string]$ErrorCode = $null,
        [int]$ExitCode = 0,
        [string]$ErrorText = "",
        [string]$OutputText = "",
        [bool]$TimedOut = $false,
        [bool]$Stopped = $false
    )

    if ([string]::IsNullOrWhiteSpace($ErrorCode)) {
        $ErrorCode = if ($Ok) { 'OK' } else { 'MEDIA_INTEGRITY_FAILED' }
    }

    [pscustomobject]@{
        Ok        = $Ok
        ErrorCode = $ErrorCode
        Reason    = $Reason
        ExitCode  = $ExitCode
        Error     = $ErrorText
        Output    = $OutputText
        TimedOut  = $TimedOut
        Stopped   = $Stopped
    }
}

function Test-FileIntegrityDetailed {
    param([string]$FilePath)
    if (-not $EnableIntegrityCheck) {
        return New-FileIntegrityResult -Ok $true -ErrorCode 'INTEGRITY_DISABLED' -Reason "Integrity check disabled"
    }
    if ([string]::IsNullOrWhiteSpace($FilePath)) {
        return New-FileIntegrityResult -Ok $false -ErrorCode 'FILE_PATH_EMPTY' -Reason "File path is empty"
    }
    if (-not (Test-Path -LiteralPath $FilePath)) {
        return New-FileIntegrityResult -Ok $false -ErrorCode 'FILE_MISSING' -Reason "File does not exist: $FilePath"
    }
    try {
        $item = Get-Item -LiteralPath $FilePath -ErrorAction Stop
        if ($item.Length -eq 0) {
            return New-FileIntegrityResult -Ok $false -ErrorCode 'FILE_ZERO_BYTES' -Reason "File is zero bytes: $FilePath"
        }

        $r = Invoke-FFprobeCommand -ArgumentList @(
            "-v","error","-show_entries","format=duration",
            "-of","default=noprint_wrappers=1:nokey=1","--",$FilePath
        ) -TimeoutSeconds 60 -Stage 'integrity-ffprobe'
        $output = ([string]$r.Output).Trim()
        $stderr = ([string]$r.Error).Trim()
        $timedOut = [bool]$r.TimedOut
        $stopped = [bool]$r.Stopped
        if ($timedOut) {
            return New-FileIntegrityResult -Ok $false -ErrorCode 'MEDIA_PROBE_TIMEOUT' -Reason "ffprobe timed out after 60s: $stderr" -ExitCode ([int]$r.ExitCode) -ErrorText $stderr -OutputText $output -TimedOut $true -Stopped $stopped
        }
        if ($stopped) {
            return New-FileIntegrityResult -Ok $false -ErrorCode 'MEDIA_PROBE_STOPPED' -Reason "ffprobe stopped by operator request: $stderr" -ExitCode ([int]$r.ExitCode) -ErrorText $stderr -OutputText $output -TimedOut $timedOut -Stopped $true
        }
        if ([int]$r.ExitCode -ne 0) {
            $reason = if ([string]::IsNullOrWhiteSpace($stderr)) { "ffprobe failed with exit $($r.ExitCode)" } else { "ffprobe failed with exit $($r.ExitCode): $stderr" }
            $code = Get-FFprobeFailureCode -ErrorText $stderr
            return New-FileIntegrityResult -Ok $false -ErrorCode $code -Reason $reason -ExitCode ([int]$r.ExitCode) -ErrorText $stderr -OutputText $output -TimedOut $timedOut -Stopped $stopped
        }
        if ([string]::IsNullOrWhiteSpace($output)) {
            return New-FileIntegrityResult -Ok $false -ErrorCode 'MEDIA_DURATION_MISSING' -Reason "ffprobe succeeded but returned no duration" -ExitCode ([int]$r.ExitCode) -ErrorText $stderr -OutputText $output -TimedOut $timedOut -Stopped $stopped
        }
        return New-FileIntegrityResult -Ok $true -ErrorCode 'OK' -Reason "ffprobe duration: $output" -ExitCode ([int]$r.ExitCode) -ErrorText $stderr -OutputText $output -TimedOut $timedOut -Stopped $stopped
    } catch {
        return New-FileIntegrityResult -Ok $false -ErrorCode 'MEDIA_INTEGRITY_EXCEPTION' -Reason "Integrity check threw: $_"
    }
}

function Test-FileIntegrity {
    param([string]$FilePath)
    $result = Test-FileIntegrityDetailed -FilePath $FilePath
    return [bool]$result.Ok
}

function Test-FileStable {
    param([string]$Path)
    if ($SkipStabilityCheck) { return $true }
    try {
        $half = [math]::Max(1, [int]($FileStabilityWait / 2))
        $s1 = (Get-Item -LiteralPath $Path -ErrorAction Stop).Length
        if (-not (Start-StopAwareSleep $half)) { return $false }
        $s2 = (Get-Item -LiteralPath $Path -ErrorAction Stop).Length
        if ($s1 -ne $s2) {
            Write-Log "File size changed in stability check ($s1 -> $s2): $Path" "DEBUG"
            return $false
        }
        if (-not (Start-StopAwareSleep $half)) { return $false }
        $s3 = (Get-Item -LiteralPath $Path -ErrorAction Stop).Length
        if ($s2 -ne $s3) {
            Write-Log "File size changed in second stability interval ($s2 -> $s3): $Path" "DEBUG"
            return $false
        }
        return $true
    } catch {
        Write-Log "Stability check failed: $Path : $_" "DEBUG"
        return $false
    }
}
