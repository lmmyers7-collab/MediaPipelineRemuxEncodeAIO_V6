# ============================================================================== 
# ops\pipeline\engine\process\tool_log_lifecycle.ps1
# ============================================================================== 
# Owns the temporary-to-terminal lifecycle for streamed native-tool diagnostics.
# Active captures are never failure evidence until a failed outcome promotes
# them. Interrupted captures remain separately retained for short-lived support
# diagnostics and are reconciled on the next exclusive startup after a hard
# process termination.
# ============================================================================== 

function Write-MediaPipelineToolLogLifecycleLog {
    param(
        [Parameter(Mandatory)] [string] $Message,
        [ValidateSet('DEBUG','INFO','WARN','ERROR')] [string] $Level = 'DEBUG'
    )

    if (Get-Command Write-Log -ErrorAction SilentlyContinue) {
        Write-Log $Message $Level
    } elseif ($Level -in @('WARN','ERROR')) {
        Write-Warning $Message
    } else {
        Write-Verbose $Message
    }
}

function ConvertTo-MediaPipelineToolLogToken {
    param(
        [AllowNull()] [string] $Value,
        [string] $Fallback = 'unknown'
    )

    $token = ([string]$Value).Trim() -replace '[^A-Za-z0-9_.-]', '_'
    $token = $token.Trim('._-')
    if ([string]::IsNullOrWhiteSpace($token)) { return $Fallback }
    return $token
}

function New-MediaPipelineToolLogCapture {
    param(
        [Parameter(Mandatory)] [string] $ToolName,
        [Parameter(Mandatory)] [string] $ActiveDirectory,
        [AllowNull()] [string] $RunId = '',
        [datetime] $Now = (Get-Date)
    )

    [System.IO.Directory]::CreateDirectory($ActiveDirectory) | Out-Null
    $toolToken = ConvertTo-MediaPipelineToolLogToken -Value $ToolName -Fallback 'tool'
    $runToken = ConvertTo-MediaPipelineToolLogToken -Value $RunId -Fallback 'run'
    $name = '{0}_active_{1}_{2}_{3}.log' -f $toolToken, $Now.ToUniversalTime().ToString('yyyyMMdd_HHmmss'), $runToken, ([guid]::NewGuid().ToString('N'))
    $path = Join-Path $ActiveDirectory $name
    [System.IO.File]::WriteAllText($path, '')
    return $path
}

function Move-MediaPipelineToolLogCapture {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string] $DestinationDirectory,
        [Parameter(Mandatory)] [string] $Disposition,
        [datetime] $Now = (Get-Date)
    )

    [System.IO.Directory]::CreateDirectory($DestinationDirectory) | Out-Null
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($Path)
    $baseName = $baseName -replace '_active_', "_${Disposition}_"
    if ($baseName -eq [System.IO.Path]::GetFileNameWithoutExtension($Path)) {
        $baseName = '{0}_{1}' -f $baseName, $Disposition
    }
    $destination = Join-Path $DestinationDirectory ('{0}{1}' -f $baseName, [System.IO.Path]::GetExtension($Path))
    if (Test-Path -LiteralPath $destination) {
        $destination = Join-Path $DestinationDirectory ('{0}_{1}{2}' -f $baseName, ([guid]::NewGuid().ToString('N')), [System.IO.Path]::GetExtension($Path))
    }
    Move-Item -LiteralPath $Path -Destination $destination -Force
    return $destination
}

function Complete-MediaPipelineToolLogCapture {
    param(
        [AllowNull()] [string] $Path,
        [Parameter(Mandatory)] [ValidateSet('success','failure','interrupted')] [string] $Disposition,
        [Parameter(Mandatory)] [string] $FailureDirectory,
        [Parameter(Mandatory)] [string] $InterruptedDirectory,
        [datetime] $Now = (Get-Date)
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return [pscustomobject][ordered]@{
            Disposition = if ($Disposition -eq 'success') { 'deleted' } else { $Disposition }
            Path        = ''
            Completed   = $false
        }
    }

    try {
        switch ($Disposition) {
            'success' {
                Remove-Item -LiteralPath $Path -Force
                return [pscustomobject][ordered]@{ Disposition = 'deleted'; Path = ''; Completed = $true }
            }
            'failure' {
                $destination = Move-MediaPipelineToolLogCapture -Path $Path -DestinationDirectory $FailureDirectory -Disposition 'failure' -Now $Now
                return [pscustomobject][ordered]@{ Disposition = 'failure'; Path = $destination; Completed = $true }
            }
            'interrupted' {
                $destination = Move-MediaPipelineToolLogCapture -Path $Path -DestinationDirectory $InterruptedDirectory -Disposition 'interrupted' -Now $Now
                return [pscustomobject][ordered]@{ Disposition = 'interrupted'; Path = $destination; Completed = $true }
            }
        }
    } catch {
        Write-MediaPipelineToolLogLifecycleLog "Could not finalize native-tool diagnostic capture '$Path' as ${Disposition}: $($_.Exception.Message)" 'WARN'
        return [pscustomobject][ordered]@{ Disposition = $Disposition; Path = $Path; Completed = $false }
    }
}

function Invoke-MediaPipelineToolLogMaintenance {
    param(
        [Parameter(Mandatory)] [string] $ActiveDirectory,
        [Parameter(Mandatory)] [string] $InterruptedDirectory,
        [ValidateRange(1,365)] [int] $RetentionDays = 3,
        [datetime] $Now = (Get-Date)
    )

    [System.IO.Directory]::CreateDirectory($ActiveDirectory) | Out-Null
    [System.IO.Directory]::CreateDirectory($InterruptedDirectory) | Out-Null
    $orphanedCount = 0
    $deletedCount = 0
    $errorCount = 0

    foreach ($capture in @(Get-ChildItem -LiteralPath $ActiveDirectory -File -ErrorAction SilentlyContinue)) {
        try {
            Move-MediaPipelineToolLogCapture -Path $capture.FullName -DestinationDirectory $InterruptedDirectory -Disposition 'interrupted' -Now $Now | Out-Null
            $orphanedCount++
        } catch {
            $errorCount++
            Write-MediaPipelineToolLogLifecycleLog "Could not reconcile orphaned native-tool diagnostic '$($capture.FullName)': $($_.Exception.Message)" 'WARN'
        }
    }

    $cutoff = $Now.ToUniversalTime().AddDays(-$RetentionDays)
    foreach ($capture in @(Get-ChildItem -LiteralPath $InterruptedDirectory -File -ErrorAction SilentlyContinue)) {
        if ($capture.LastWriteTimeUtc -ge $cutoff) { continue }
        try {
            Remove-Item -LiteralPath $capture.FullName -Force
            $deletedCount++
        } catch {
            $errorCount++
            Write-MediaPipelineToolLogLifecycleLog "Could not remove expired interrupted native-tool diagnostic '$($capture.FullName)': $($_.Exception.Message)" 'WARN'
        }
    }

    return [pscustomobject][ordered]@{
        OrphanedCount = $orphanedCount
        DeletedCount  = $deletedCount
        ErrorCount    = $errorCount
        RetentionDays = $RetentionDays
    }
}
