# Extracted from ops/pipeline/entrypoints/Audit-MediaLibrary.ps1. Responsibility: native command lifecycle and audit logging

function Write-AuditLog {
    param(
        [string]$Message,
        [ValidateSet('INFO','WARN','ERROR','DEBUG')] [string] $Level = 'INFO'
    )

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "$timestamp [$Level] $Message"
    switch ($Level) {
        'ERROR' { Write-Host $line -ForegroundColor Red }
        'WARN'  { Write-Host $line -ForegroundColor Yellow }
        'DEBUG' { Write-Host $line -ForegroundColor Gray }
        default { Write-Host $line }
    }
}

function Resolve-ExecutablePath {
    param(
        [string]$Name,
        [string[]]$RelativeCandidates = @()
    )

    foreach ($relative in $RelativeCandidates) {
        $candidate = Join-Path $PSScriptRoot $relative
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    if (-not $script:AuditAllowSystemTools) {
        throw "Required bundled executable '$Name' was not found. Set AllowSystemTools=true only for development fallback."
    }

    $command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) { return $command.Source }

    throw "Required executable '$Name' was not found in the bundle or on PATH."
}

function Stop-AuditProcessTree {
    param(
        [System.Diagnostics.Process]$Process,
        [string]$Label = "process"
    )
    if ($null -eq $Process) { return }
    try { if ($Process.HasExited) { return } } catch {}

    $pidText = try { [string]$Process.Id } catch { "" }
    try {
        $Process.Kill($true)
        return
    } catch {
        Write-AuditLog "Kill(true) failed for $Label PID $pidText : $($_.Exception.Message)" 'DEBUG'
    }
    if ($pidText -and (Get-Command taskkill.exe -ErrorAction SilentlyContinue)) {
        try {
            & taskkill.exe /PID $pidText /T /F 2>&1 | Out-Null
            return
        } catch {
            Write-AuditLog "taskkill fallback failed for $Label PID $pidText : $($_.Exception.Message)" 'DEBUG'
        }
    }
    try { $Process.Kill() } catch {}
}

function Get-CompletedAuditTaskText {
    param(
        [object]$Task,
        [int]$WaitMilliseconds = 1000
    )
    if ($null -eq $Task) { return "" }
    try {
        if ($Task.IsCompleted -or $Task.Wait($WaitMilliseconds)) {
            return [string]$Task.Result
        }
    } catch {}
    return ""
}

function Invoke-AuditNativeCommand {
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [Parameter(Mandatory)] [array]$ArgumentList,
        [int]$TimeoutSeconds = 60
    )

    $psi = [System.Diagnostics.ProcessStartInfo]@{
        FileName               = $FilePath
        UseShellExecute        = $false
        RedirectStandardOutput = $true
        RedirectStandardError  = $true
        CreateNoWindow         = $true
    }
    foreach ($arg in $ArgumentList) { $psi.ArgumentList.Add([string]$arg) }

    $proc = $null
    $stdoutTask = $null
    $stderrTask = $null
    $timedOut = $false
    $startedAt = Get-Date
    try {
        $proc = [System.Diagnostics.Process]::Start($psi)
        $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
        $stderrTask = $proc.StandardError.ReadToEndAsync()
        while (-not $proc.HasExited) {
            if ($TimeoutSeconds -gt 0 -and ((Get-Date) - $startedAt).TotalSeconds -ge $TimeoutSeconds) {
                $timedOut = $true
                Stop-AuditProcessTree -Process $proc -Label (Split-Path $FilePath -Leaf)
                break
            }
            Start-Sleep -Milliseconds 100
        }
        if ($timedOut) { try { $proc.WaitForExit(5000) | Out-Null } catch {} }
        else           { try { $proc.WaitForExit() } catch {} }
    } catch {
        $stderr = "Failed to start ${FilePath}: $_"
        return @{
            ExitCode  = -2
            Output    = ""
            Error     = $stderr
            Stdout    = ""
            Stderr    = $stderr
            TimedOut  = $false
            Stopped   = $false
            ErrorCode = 'NATIVE_START_FAILED'
        }
    }

    $stdout = Get-CompletedAuditTaskText -Task $stdoutTask
    $stderr = Get-CompletedAuditTaskText -Task $stderrTask
    if ($timedOut) {
        $stderr = ($stderr + "`n[KILLED: TIMEOUT after ${TimeoutSeconds}s]").Trim()
        return @{
            ExitCode  = -1
            Output    = $stdout
            Error     = $stderr
            Stdout    = $stdout
            Stderr    = $stderr
            TimedOut  = $true
            Stopped   = $false
            ErrorCode = 'NATIVE_TIMEOUT'
        }
    }
    $exitCode = $proc.ExitCode
    $errorCode = if ($exitCode -eq 0) { 'OK' } else { "NATIVE_EXIT_$exitCode" }
    return @{
        ExitCode  = $exitCode
        Output    = $stdout
        Error     = $stderr
        Stdout    = $stdout
        Stderr    = $stderr
        TimedOut  = $false
        Stopped   = $false
        ErrorCode = $errorCode
    }
}
