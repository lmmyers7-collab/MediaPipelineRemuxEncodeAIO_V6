# Extracted from ops/pipeline/engine/decide/encode_policy.ps1. Responsibility: CPU mutex and hardware-failure retry policy

function Acquire-CpuEncodeMutex {
    <#
    .SYNOPSIS
    F-new-4 — Hold a machine-wide mutex while a CPU encode is running.

    .DESCRIPTION
    A single libx265 job already saturates every logical core on most
    hardware. If two pipeline workers (e.g. coordinator + remote worker
    on the same box) both pick up CPU-routed jobs concurrently, the box
    will thrash, the desktop GUI's main loop will starve, and both
    encodes will run slower than serialized. This helper takes a Win32
    mutex (`Global\MediaPipelineCpuEncodeMutex` by default) before the
    libx265 invocation and releases it afterwards. The mutex is opened
    by name so any process on the same machine sees the same handle.

    The TimeoutSeconds parameter is the maximum time we'll block waiting
    for another CPU encode to finish. -1 = wait forever. 0 = give up
    immediately. Returns a [pscustomobject] with `Acquired: $true|$false`
    and a `Release` scriptblock that the caller invokes in `finally`.
    #>
    param(
        [string] $Name = 'Global\MediaPipelineCpuEncodeMutex',
        [int]    $TimeoutSeconds = -1
    )

    try {
        $mutex = [System.Threading.Mutex]::new($false, $Name)
    } catch {
        # OpenExisting/named-mutex creation can fail on locked-down
        # systems (Group Policy, AppContainer). Fail open so a single
        # broken environment doesn't strand the encode entirely; we
        # log a warning and let the encode proceed without the lock.
        Write-Log "CPU-encode mutex unavailable ($($_.Exception.Message)); continuing without serialization" "WARN"
        return [pscustomobject]@{
            Acquired = $false
            Reason   = "mutex creation failed: $($_.Exception.Message)"
            Release  = { }
        }
    }

    $waitMs = if ($TimeoutSeconds -lt 0) { -1 } else { [int]([math]::Min([int]::MaxValue, [double]$TimeoutSeconds * 1000)) }
    $acquired = $false
    try {
        $acquired = $mutex.WaitOne($waitMs)
    } catch [System.Threading.AbandonedMutexException] {
        # An earlier holder exited without releasing (process killed mid-
        # encode). WaitOne returns true after this exception, so we own
        # the mutex now.
        $acquired = $true
        Write-Log "CPU-encode mutex was abandoned by a previous holder; recovered ownership" "WARN"
    } catch {
        Write-Log "CPU-encode mutex wait failed: $($_.Exception.Message)" "WARN"
        $acquired = $false
    }

    if (-not $acquired) {
        try { $mutex.Dispose() } catch {}
        return [pscustomobject]@{
            Acquired = $false
            Reason   = "wait timed out after ${TimeoutSeconds}s"
            Release  = { }
        }
    }

    $release = {
        try { $mutex.ReleaseMutex() } catch {}
        try { $mutex.Dispose() } catch {}
    }.GetNewClosure()
    return [pscustomobject]@{
        Acquired = $true
        Reason   = ''
        Release  = $release
    }
}

function Test-IsHardwareEncoderFailure {
    param(
        [string] $Encoder = '',
        [string] $ErrorText = ''
    )

    if ([string]::IsNullOrWhiteSpace($ErrorText)) { return $false }
    $encoderText = ([string]$Encoder).Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($encoderText) -or $encoderText -match 'nvenc') {
        return (Test-IsNvencError $ErrorText)
    }

    $patterns = @()
    if ($encoderText -match 'amf') {
        $patterns = @(
            'AMF',
            'Advanced Media Framework',
            'CreateComponent.*failed',
            'failed to (initialise|initialize).*amf',
            'encoder initialization failed',
            'No device available',
            'device.*failed',
            'hardware.*(unavailable|failed)'
        )
    } elseif ($encoderText -match 'qsv') {
        $patterns = @(
            'qsv',
            'MFX_ERR',
            'Error initializing (an )?(internal )?MFX session',
            'unsupported device',
            'No device available',
            'device.*failed',
            'hardware.*(unavailable|failed)'
        )
    } else {
        return $false
    }

    foreach ($pattern in $patterns) {
        if ($ErrorText -match $pattern) { return $true }
    }
    return $false
}

function Test-ShouldRetryEncodeWithCpuFallback {
    param(
        [bool] $Success = $false,
        [bool] $StopRequested = $false,
        [string] $VideoCodec = '',
        [string] $ErrorText = '',
        # When set, the gate fires regardless of the stderr pattern.
        # Used by Do-Encode to short-circuit the primary GPU attempt when
        # the cached NVENC probe (Test-NvencProbeReportsAvailable) has
        # been invalidated by a previous file's runtime failure.
        [bool] $ForceCpu = $false
    )

    if ($Success) { return $false }
    if ($StopRequested) { return $false }
    if ($ForceCpu) { return $true }
    return (Test-IsHardwareEncoderFailure -Encoder $VideoCodec -ErrorText $ErrorText)
}
