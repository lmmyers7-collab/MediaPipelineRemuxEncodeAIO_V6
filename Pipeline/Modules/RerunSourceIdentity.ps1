function Write-RerunIdentityLog {
    param([string]$Message, [string]$Level = 'INFO')
    if (Get-Command Write-RerunLog -ErrorAction SilentlyContinue) {
        Write-RerunLog -Message $Message -Level $Level
    } else {
        Write-Verbose "[$Level] $Message"
    }
}

function Stop-RerunNativeProcessTree {
    param(
        [System.Diagnostics.Process]$Process,
        [string]$Label = 'process'
    )
    if ($null -eq $Process) { return }
    try { if ($Process.HasExited) { return } } catch {}
    try {
        $Process.Kill($true)
        return
    } catch {
        Write-RerunIdentityLog "Kill(true) failed for $Label PID $($Process.Id): $_" "WARN"
    }
    try {
        & taskkill.exe /PID ([string]$Process.Id) /T /F 2>$null | Out-Null
        return
    } catch {
        Write-RerunIdentityLog "taskkill fallback failed for $Label PID $($Process.Id): $_" "WARN"
    }
    try { $Process.Kill() } catch {}
}

function Get-RerunCompletedTaskText {
    param(
        [object]$Task,
        [int]$WaitMilliseconds = 1000
    )
    if ($null -eq $Task) { return '' }
    try {
        if ($Task.IsCompleted -or $Task.Wait($WaitMilliseconds)) {
            return [string]$Task.Result
        }
    } catch {}
    return ''
}

function Invoke-RerunNativeCommand {
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [array]$ArgumentList = @(),
        [int]$TimeoutSeconds = 0,
        [string]$Label = ''
    )
    $psi = [System.Diagnostics.ProcessStartInfo]@{
        FileName               = $FilePath
        UseShellExecute        = $false
        RedirectStandardError  = $true
        RedirectStandardOutput = $true
        CreateNoWindow         = $true
    }
    foreach ($arg in @($ArgumentList)) {
        [void]$psi.ArgumentList.Add([string]$arg)
    }

    $proc = $null
    $stdoutTask = $null
    $stderrTask = $null
    $startedAt = Get-Date
    $timedOut = $false
    try {
        $proc = [System.Diagnostics.Process]::Start($psi)
        $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
        $stderrTask = $proc.StandardError.ReadToEndAsync()
        while (-not $proc.HasExited) {
            if ($TimeoutSeconds -gt 0 -and ((Get-Date) - $startedAt).TotalSeconds -ge $TimeoutSeconds) {
                $timedOut = $true
                Stop-RerunNativeProcessTree -Process $proc -Label $(if ($Label) { $Label } else { (Split-Path $FilePath -Leaf) })
                break
            }
            Start-Sleep -Milliseconds 100
        }
        if ($timedOut) {
            try { $proc.WaitForExit(5000) | Out-Null } catch {}
        } else {
            try { $proc.WaitForExit() } catch {}
        }
    } catch {
        return [pscustomobject]@{
            ExitCode = -2
            Output   = ''
            Error    = "Failed to start native command '$FilePath': $_"
            TimedOut = $false
        }
    }

    $stdout = Get-RerunCompletedTaskText -Task $stdoutTask -WaitMilliseconds 1000
    $stderr = Get-RerunCompletedTaskText -Task $stderrTask -WaitMilliseconds 1000
    if ($timedOut) {
        $stderr = ($stderr + "`n[KILLED: TIMEOUT after ${TimeoutSeconds}s]").Trim()
    }
    return [pscustomobject]@{
        ExitCode = if ($timedOut) { -1 } else { [int]$proc.ExitCode }
        Output   = $stdout
        Error    = $stderr
        TimedOut = $timedOut
    }
}

function Get-RerunSourceSampleHash {
    param([string]$Path, [long]$Size, [int]$SampleBytes = 1048576)
    $stream = $null
    $sha = $null
    try {
        $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        $sha = [System.Security.Cryptography.SHA256]::Create()
        $sampleByteCount = [int][math]::Max(1, $SampleBytes)
        $buffer = [byte[]]::new($sampleByteCount)
        $read = $stream.Read($buffer, 0, [int][math]::Min([int64]$buffer.Length, [math]::Min([int64]$Size, [int64]$SampleBytes)))
        if ($read -gt 0) { [void]$sha.TransformBlock($buffer, 0, $read, $buffer, 0) }
        if ($Size -gt $SampleBytes) {
            [void]$stream.Seek([math]::Max([int64]0, [int64]$Size - [int64]$SampleBytes), [System.IO.SeekOrigin]::Begin)
            $read = $stream.Read($buffer, 0, [int][math]::Min([int64]$buffer.Length, [int64]$SampleBytes))
            if ($read -gt 0) { [void]$sha.TransformBlock($buffer, 0, $read, $buffer, 0) }
        }
        [void]$sha.TransformFinalBlock([byte[]]::new(0), 0, 0)
        return -join ($sha.Hash | ForEach-Object { $_.ToString('x2') })
    } catch {
        Write-RerunIdentityLog "Source sample hash failed for $Path : $_" "WARN"
        return ''
    } finally {
        if ($stream) { $stream.Dispose() }
        if ($sha) { $sha.Dispose() }
    }
}

function Get-RerunSourceIdentityV2 {
    param(
        [System.IO.FileInfo]$FileInfo,
        [string]$FfprobePath,
        [int]$TimeoutSeconds = 30
    )
    if (-not $FfprobePath -or -not (Test-Path -LiteralPath $FfprobePath)) { return '' }

    $duration = 0.0
    $codec = ''
    try {
        $probeResult = Invoke-RerunNativeCommand -FilePath $FfprobePath -ArgumentList @(
            '-v', 'error',
            '-show_entries', 'format=duration:stream=codec_type,codec_name',
            '-of', 'json',
            '--', $FileInfo.FullName
        ) -TimeoutSeconds $TimeoutSeconds -Label 'ffprobe-rerun-identity'
        if ($probeResult.TimedOut) {
            Write-RerunIdentityLog "ffprobe identity check timed out after ${TimeoutSeconds}s for $($FileInfo.FullName)" "WARN"
        } elseif ([int]$probeResult.ExitCode -eq 0 -and $probeResult.Output) {
            $probe = ($probeResult.Output | ConvertFrom-Json -ErrorAction Stop)
            try { $duration = [double]$probe.format.duration } catch {}
            foreach ($stream in @($probe.streams)) {
                if ([string]$stream.codec_type -eq 'video') {
                    $codec = [string]$stream.codec_name
                    break
                }
            }
        } elseif ([int]$probeResult.ExitCode -ne 0) {
            Write-RerunIdentityLog "ffprobe identity check failed for $($FileInfo.FullName) with exit $($probeResult.ExitCode): $($probeResult.Error)" "WARN"
        }
    } catch {
        Write-RerunIdentityLog "ffprobe identity check failed for $($FileInfo.FullName): $_" "WARN"
    }

    $sampleHash = Get-RerunSourceSampleHash -Path $FileInfo.FullName -Size ([long]$FileInfo.Length)
    $fingerprint = "{0}|duration={1}|vcodec={2}|sample={3}" -f `
        [long]$FileInfo.Length,
        ([math]::Round($duration, 3)).ToString([System.Globalization.CultureInfo]::InvariantCulture),
        $codec.ToLowerInvariant(),
        $sampleHash
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($fingerprint)
        return -join ($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') })
    } finally {
        if ($sha) { $sha.Dispose() }
    }
}
