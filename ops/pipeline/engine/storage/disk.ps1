# ==============================================================================
# ops\pipeline\engine\storage\disk.ps1
# ==============================================================================
# Disk-space probes extracted from MediaPipeline.ps1.
#
# Dot-sourced from the main script. Reads the following from the shared
# scope at call time:
#
#   Test-IsUncPath, Get-UncShareRoot   — ops\pipeline\engine\shared\path_helpers.ps1
#   Invoke-NativeCommand, Start-StopAwareSleep — ops\pipeline\engine\shared\native.ps1
#   Write-Log                          — ops\pipeline\engine\observability\logging.ps1
#   $script:MinFreeSpaceGB             — config (Test-DiskSpace default)
#   $script:OutputSizeMultiplier       — config (encode estimate)
#   $script:RobocopyTimeoutSeconds     — config (Copy-FileRobocopy)
#   $script:CleanupRemoteStaging       — config (Clear-StalePartialFiles)
#   $script:CleanupStaleAgeHours       — config (Clear-StalePartialFiles)
#   $script:CleanupScanTimeoutSeconds  — config (Clear-StalePartialFiles)
#   $MinFreeSpaceGB                    — config (Test-EstimatedOutputSpace headroom)
#
# History (from the v1.0 changelog):
#
#   FIX#2  — UNC paths used to silently report "enough space" because
#            the old [Get-FreeSpaceGB] only handled drive letters
#            ([A-Za-z]:\). The outsource share could fill up mid-copy
#            and corrupt files. Replaced with a path-type-aware probe
#            that calls kernel32!GetDiskFreeSpaceExW for UNC roots and
#            [System.IO.DriveInfo] for local drive letters.
#
# Why a P/Invoke for UNC?
#   [System.IO.DriveInfo] only knows about local DriveType.Fixed/Network
#   drives that have been mounted with a drive letter. A bare \\srv\share
#   path returns DriveType=Unknown and AvailableFreeSpace throws.
#   GetDiskFreeSpaceExW accepts any directory path including UNC roots,
#   handles per-user quotas correctly (the lpFreeBytesAvailable out-param),
#   and is the documented Win32 way to do this.
#
# Why bound the UNC probe in a child job?
#   GetDiskFreeSpaceExW on an unreachable SMB share blocks until the SMB
#   stack times out (default ~60 s on Windows). Wrapping in Start-Job +
#   Wait-Job means a single dead share cannot wedge the main loop.
# ==============================================================================

# The C# source is kept as a script-scope variable because Get-UncFreeSpaceGBBounded
# also needs it — when the probe job runs in a child PowerShell process, it
# has to re-Add-Type the same definition there. Storing it once avoids
# duplicating the literal between two functions.
$script:DiskSpaceTypeDefinition = @"
using System;
using System.Runtime.InteropServices;
namespace MediaPipeline {
    public static class DiskSpace {
        [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool GetDiskFreeSpaceExW(
            string lpDirectoryName,
            out ulong lpFreeBytesAvailable,
            out ulong lpTotalNumberOfBytes,
            out ulong lpTotalNumberOfFreeBytes);
    }
}
"@
if (-not ('MediaPipeline.DiskSpace' -as [type])) {
    Add-Type -TypeDefinition $script:DiskSpaceTypeDefinition -Language CSharp
}

# Free space on the drive or share containing $Path, in GB, or -1 if it
# can't be determined. Thin alias to Get-FreeSpaceGBAny preserved for
# callers that were already using the old name.
function Get-FreeSpaceGB {
    param([string]$Path)
    return Get-FreeSpaceGBAny $Path
}

function Get-RobocopyProcessWriteByteCount {
    param([object]$Process)
    try {
        if ($null -eq $Process) { return $null }
        $pidValue = [int]$Process.Id
        if ($pidValue -le 0) { return $null }
        $row = Get-CimInstance -ClassName Win32_PerfRawData_PerfProc_Process -Filter "IDProcess=$pidValue" -ErrorAction Stop |
            Select-Object -First 1
        if ($null -eq $row -or $null -eq $row.IOWriteBytesPersec) { return $null }
        $bytes = [long]$row.IOWriteBytesPersec
        if ($bytes -lt 0) { return $null }
        return $bytes
    } catch {
        return $null
    }
}

function Resolve-RobocopyActiveCopyProgressBytes {
    param(
        [long]$LandedBytes,
        [long]$TotalBytes,
        [long]$LastProgressBytes,
        [object]$CurrentProcessWriteBytes = $null,
        [object]$LastProcessWriteBytes = $null
    )
    if ($TotalBytes -le 0) {
        return [math]::Max(0L, $LandedBytes)
    }

    $maxActiveBytes = [math]::Max(0L, $TotalBytes - 1L)
    $safeLast = [math]::Max(0L, [math]::Min($LastProgressBytes, $maxActiveBytes))
    $safeLanded = [math]::Max(0L, $LandedBytes)

    if ($safeLanded -lt $TotalBytes) {
        return [math]::Min($maxActiveBytes, [math]::Max($safeLast, $safeLanded))
    }

    $currentWrite = $null
    try {
        if ($null -ne $CurrentProcessWriteBytes -and "$CurrentProcessWriteBytes" -ne '') {
            $currentWrite = [long]$CurrentProcessWriteBytes
        }
    } catch { $currentWrite = $null }

    if ($null -ne $currentWrite -and $currentWrite -gt 0) {
        $previousWrite = $null
        try {
            if ($null -ne $LastProcessWriteBytes -and "$LastProcessWriteBytes" -ne '') {
                $previousWrite = [long]$LastProcessWriteBytes
            }
        } catch { $previousWrite = $null }
        $delta = if ($null -eq $previousWrite) { $currentWrite } else { $currentWrite - $previousWrite }
        if ($delta -gt 0) {
            return [math]::Min($maxActiveBytes, $safeLast + $delta)
        }
    }

    return $safeLast
}

# UNC free-space probe wrapped in Start-Job. Returns the rounded GB value
# on success, -1 on probe failure or timeout. Works whether the share is
# accessed by IP (\\10.0.0.1\Media) or name (\\nas\media).
function Get-UncFreeSpaceGBBounded {
    param(
        [string]$Path,
        [int]$TimeoutSeconds = 10
    )
    $probe = Get-UncShareRoot $Path
    if ([string]::IsNullOrWhiteSpace($probe)) { return -1 }

    $job = Start-Job -ScriptBlock {
        param($probePath, $typeDefinition)
        try {
            if (-not ('MediaPipeline.DiskSpace' -as [type])) {
                Add-Type -TypeDefinition $typeDefinition -Language CSharp
            }
            [uint64]$freeAvail  = 0
            [uint64]$totalBytes = 0
            [uint64]$totalFree  = 0
            $ok = [MediaPipeline.DiskSpace]::GetDiskFreeSpaceExW(
                $probePath, [ref]$freeAvail, [ref]$totalBytes, [ref]$totalFree)
            if (-not $ok) { return -1 }
            return [math]::Round($freeAvail / 1GB, 2)
        } catch {
            return -1
        }
    } -ArgumentList $probe, $script:DiskSpaceTypeDefinition

    try {
        if (Wait-Job $job -Timeout $TimeoutSeconds) {
            $result = Receive-Job $job -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($null -ne $result) { return [double]$result }
            return -1
        }
        Stop-Job $job -ErrorAction SilentlyContinue
        Write-Log "Get-FreeSpaceGBAny: UNC free-space probe timed out after ${TimeoutSeconds}s for '$probe'" "WARN"
        return -1
    } finally {
        Remove-Job $job -Force -ErrorAction SilentlyContinue
    }
}

# Path-type-aware free-space dispatcher. Returns -1 to mean "indeterminate"
# so callers can tell genuine "0 GB free" apart from probe failure.
function Get-FreeSpaceGBAny {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return -1 }

    if (Test-IsUncPath $Path) {
        return Get-UncFreeSpaceGBBounded -Path $Path -TimeoutSeconds 10
    }

    # Local drive-letter paths: use [System.IO.DriveInfo].
    # Pure .NET, no P/Invoke required, and it correctly returns 0 when the
    # drive is full rather than failing.
    if ($Path -match '^([A-Za-z]):[/\\]?') {
        try {
            $di = [System.IO.DriveInfo]::new($Matches[1])
            return [math]::Round($di.AvailableFreeSpace / 1GB, 2)
        } catch {
            Write-Log "Get-FreeSpaceGBAny: DriveInfo failed for '$Path': $_" "WARN"
            return -1
        }
    }

    return -1
}

# Threshold check used by Copy-FileRobocopy and the encode/remux entry points
# to fail fast when the destination is critically low on space. Indeterminate
# probes fail closed; proceeding after a disconnected share or failed local
# free-space query risks partial copy/encode work and confusing retry loops.
function Test-DiskSpace {
    param([string]$Path, [double]$MinGB = $script:MinFreeSpaceGB, [string]$Label = "LOCAL")
    try {
        $freeGB = Get-FreeSpaceGBAny $Path
        if ($freeGB -lt 0) {
            Write-Log ("{0}: unable to determine free space at '{1}' - refusing to continue" `
                -f $Label, $Path) "ERROR"
            return $false
        }
        if ($freeGB -lt $MinGB) {
            Write-Log ("{0} LOW DISK SPACE: {1:N2} GB free, need {2:N2} GB at {3}" `
                -f $Label, $freeGB, $MinGB, $Path) "ERROR"
            return $false
        }
        return $true
    } catch {
        Write-Log "Disk space check failed for $Path : $_" "ERROR"
        return $false
    }
}

# Pre-encode disk-space check. Estimates output size at sourceSize *
# OutputSizeMultiplier (default 0.7x for HEVC at CQ 22) and ensures the
# scratch drive has room for both the estimated output AND the configured
# headroom, instead of crashing mid-encode at 80%. Treats indeterminate
# probes as "skip" rather than "proceed" — the alternative is FFmpeg
# exiting -22 (EINVAL) at the end of a multi-hour encode.
#
# F-new-1 — when the caller knows the encode will run on CPU (libx265
# fallback or a future CPU-primary route), pass -IsCpuEncode to inflate the
# multiplier. NVENC at CQ 22 lands ~0.55–0.75x source; libx265 at CRF 20
# medium with grain/animation lands 0.85–1.05x. Same 0.7x ceiling for both
# routinely green-lights an encode that fills the scratch volume at 95%.
function Test-EstimatedOutputSpace {
    param(
        [string]$SourcePath,
        [string]$Label = "ENCODE",
        [switch]$IsCpuEncode,
        # R1/R10 — Remux is a two-stage pipeline (ffmpeg -> temp_av MKV ->
        # mkvmerge -> final MKV). Peak scratch usage is roughly:
        #   1.0x (input scratch copy) + ~1.0x (temp_av) + ~1.0x (final)
        # Reserve 2.5x source so a 50 GB UHD source on a 50 GB-headroom
        # volume cannot fill the disk at 90% mkvmerge.
        [switch]$RemuxTwoStage,
        # When set, halve the multiplier (used for the second-stage check
        # between AV success and mkvmerge — the input is now redundant
        # but temp_av + final still need room).
        [switch]$RemuxFinalStage
    )
    if (-not (Test-Path -LiteralPath $SourcePath)) { return $false }
    try {
        $sourceGB   = (Get-Item -LiteralPath $SourcePath).Length / 1GB
        $baseMult   = [double]$script:OutputSizeMultiplier
        # CPU multiplier: take the larger of (configured-multiplier * 1.4)
        # and 1.0 so we always reserve at least 1:1 headroom for CPU
        # output. Capped at 2.0 to match the schema's max.
        $effectiveMult = if ($RemuxTwoStage) {
            # AV temp_av (~1.0x) + final (~1.0x) + small subtitle inflation
            2.5
        } elseif ($RemuxFinalStage) {
            # temp_av is on disk already; final still to be written.
            # source headroom is implicitly counted by the existing temp_av.
            1.1
        } elseif ($IsCpuEncode) {
            [math]::Min(2.0, [math]::Max(1.0, $baseMult * 1.4))
        } else {
            $baseMult
        }
        $estOutGB   = $sourceGB * $effectiveMult
        $freeGB     = Get-FreeSpaceGB $SourcePath
        $needGB     = $estOutGB + $MinFreeSpaceGB
        $multSuffix = if ($RemuxTwoStage) {
            "x (remux two-stage: input + temp_av + final)"
        } elseif ($RemuxFinalStage) {
            "x (remux final stage: temp_av already on disk)"
        } elseif ($IsCpuEncode) {
            "x (CPU-aware)"
        } else {
            "x"
        }
        if ($freeGB -lt 0) {
            Write-Log ("{0}: unable to determine free space at '{1}' — skipping to avoid mid-run failure" `
                -f $Label, $SourcePath) "ERROR"
            return $false
        }
        if ($freeGB -lt $needGB) {
            Write-Log ("{0}: insufficient space (free {1:N1} GB, need ~{2:N1} GB: {3:N1} GB est output @ {4:N2}{5} + {6} GB headroom)" `
                -f $Label, $freeGB, $needGB, $estOutGB, $effectiveMult, $multSuffix, $MinFreeSpaceGB) "ERROR"
            return $false
        }
        Write-Log ("{0}: space check OK (free {1:N1} GB, est output {2:N1} GB @ {3:N2}{4})" `
            -f $Label, $freeGB, $estOutGB, $effectiveMult, $multSuffix) "DEBUG"
        return $true
    } catch {
        Write-Log "${Label}: space check failed ($_) - skipping to avoid mid-run failure" "ERROR"
        return $false
    }
}

function Resolve-RobocopyPath {
    $systemRoot = if ($env:SystemRoot) { [string]$env:SystemRoot } else { [string]$env:windir }
    if ([string]::IsNullOrWhiteSpace($systemRoot)) {
        Write-Log "Cannot resolve robocopy.exe: SystemRoot is not set" "ERROR"
        return $null
    }
    $robocopyPath = Join-Path $systemRoot 'System32\robocopy.exe'
    if (-not (Test-Path -LiteralPath $robocopyPath -PathType Leaf -ErrorAction SilentlyContinue)) {
        Write-Log "Cannot resolve robocopy.exe at expected system path: $robocopyPath" "ERROR"
        return $null
    }
    return $robocopyPath
}

function Get-MediaPipelineCopyScriptVariableText {
    param([string]$Name)

    $variable = Get-Variable -Name $Name -Scope Script -ErrorAction SilentlyContinue
    if ($variable -and -not [string]::IsNullOrWhiteSpace([string]$variable.Value)) {
        return [string]$variable.Value
    }
    return ''
}

function Get-MediaPipelineCopyDestinationRootCandidates {
    $roots = [System.Collections.Generic.List[object]]::new()
    $seen = @{}
    $addRoot = {
        param([string]$Label, [string]$Root)
        if ([string]::IsNullOrWhiteSpace($Root)) { return }
        $rootText = Normalize-MediaPipelinePathForBoundary $Root
        if ([string]::IsNullOrWhiteSpace($rootText)) { return }
        $key = $rootText.ToLowerInvariant()
        if ($seen.ContainsKey($key)) { return }
        $seen[$key] = $true
        $roots.Add([pscustomobject]@{ Label = $Label; Root = $Root; NormalizedRoot = $rootText }) | Out-Null
    }

    foreach ($name in @('processingDir', 'LocalEncoded', 'LocalPendingPush', 'LocalRemuxTemp', 'LocalBase')) {
        & $addRoot $name (Get-MediaPipelineCopyScriptVariableText -Name $name)
    }

    if (Get-Command -Name Get-MediaPipelineLibraryProfiles -ErrorAction SilentlyContinue) {
        foreach ($profile in @(Get-MediaPipelineLibraryProfiles)) {
            if (-not $profile) { continue }
            $outputRoot = if (Get-Command -Name Get-MediaPipelineProfileProperty -ErrorAction SilentlyContinue) {
                [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'output_path' -Default '')
            } elseif ($profile.PSObject.Properties['output_path']) {
                [string]$profile.output_path
            } else {
                ''
            }
            & $addRoot 'LibraryProfiles.output_path' $outputRoot
        }
    }

    & $addRoot 'Outsource' (Get-MediaPipelineCopyScriptVariableText -Name 'Outsource')

    return @($roots)
}

function Resolve-MediaPipelineCopyDestinationRoot {
    param([string]$Destination)

    if ([string]::IsNullOrWhiteSpace($Destination)) { return $null }
    $matches = @()
    foreach ($candidate in @(Get-MediaPipelineCopyDestinationRootCandidates)) {
        if (-not $candidate -or [string]::IsNullOrWhiteSpace([string]$candidate.Root)) { continue }
        if (Test-MediaPipelinePathIsEqualOrChild -Path $Destination -Root ([string]$candidate.Root)) {
            $matches += $candidate
        }
    }
    if (@($matches).Count -le 0) { return $null }
    return @($matches | Sort-Object @{ Expression = { ([string]$_.NormalizedRoot).Length }; Descending = $true } | Select-Object -First 1)[0]
}

function Copy-FileRobocopy {
    param([string]$Source, [string]$Destination, [int]$MaxRetries = 3)
    $script:LastCopyFileRobocopyResult = [pscustomobject]@{
        Ok                = $false
        ReasonCode        = ''
        Reason            = ''
        Source            = $Source
        Destination       = $Destination
        DestinationFreeGB = $null
        RequiredGB        = $null
        Attempts          = 0
        BytesCopied       = $null
        TotalBytes        = $null
        Percent           = $null
        ProgressAvailable = $false
    }

    # Copy into a unique staging directory first. Robocopy cannot rename the
    # copied file, so copying directly into $dstDir can expose or overwrite the
    # final MKV when source/destination leaf names match.
    $srcDir  = Split-Path $Source -Parent
    $srcFile = Split-Path $Source -Leaf
    $dstDir  = Split-Path $Destination -Parent
    $dstBase = Split-Path $Destination -Leaf
    $stagingRoot = Join-Path $dstDir ".mediapipeline-staging"
    $robocopyPath = Resolve-RobocopyPath
    if ([string]::IsNullOrWhiteSpace($robocopyPath)) {
        $script:LastCopyFileRobocopyResult.ReasonCode = 'ROBOCOPY_NOT_FOUND'
        $script:LastCopyFileRobocopyResult.Reason = 'robocopy.exe was not found at the expected System32 path'
        return $false
    }

    $sourceBoundary = Test-MediaPipelinePathBoundarySafe -Path $Source -Root $srcDir
    if (-not $sourceBoundary.Ok) {
        $reason = "Copy source path failed boundary guard ($($sourceBoundary.ReasonCode)): $Source"
        Write-Log $reason "ERROR"
        $script:LastCopyFileRobocopyResult.ReasonCode = 'COPY_SOURCE_PATH_UNSAFE'
        $script:LastCopyFileRobocopyResult.Reason = $reason
        return $false
    }
    $destinationRoot = Resolve-MediaPipelineCopyDestinationRoot -Destination $Destination
    if (-not $destinationRoot) {
        $reason = "Copy destination path is outside configured copy roots: $Destination"
        Write-Log $reason "ERROR"
        $script:LastCopyFileRobocopyResult.ReasonCode = 'COPY_DESTINATION_ROOT_UNTRUSTED'
        $script:LastCopyFileRobocopyResult.Reason = $reason
        return $false
    }
    $destinationBoundary = Test-MediaPipelinePathBoundarySafe -Path $Destination -Root ([string]$destinationRoot.Root) -AllowMissingLeaf
    if (-not $destinationBoundary.Ok) {
        $reason = "Copy destination path failed boundary guard ($($destinationBoundary.ReasonCode)): $Destination"
        Write-Log $reason "ERROR"
        $script:LastCopyFileRobocopyResult.ReasonCode = 'COPY_DESTINATION_PATH_UNSAFE'
        $script:LastCopyFileRobocopyResult.Reason = $reason
        return $false
    }
    $stagingBoundary = Test-MediaPipelinePathBoundarySafe -Path $stagingRoot -Root ([string]$destinationRoot.Root) -AllowMissingLeaf
    if (-not $stagingBoundary.Ok) {
        $reason = "Copy staging path failed boundary guard ($($stagingBoundary.ReasonCode)): $stagingRoot"
        Write-Log $reason "ERROR"
        $script:LastCopyFileRobocopyResult.ReasonCode = 'COPY_STAGING_PATH_UNSAFE'
        $script:LastCopyFileRobocopyResult.Reason = $reason
        return $false
    }
    if (-not (Test-Path -LiteralPath $dstDir)) { [System.IO.Directory]::CreateDirectory($dstDir) | Out-Null }
    if (-not (Test-Path -LiteralPath $stagingRoot)) { [System.IO.Directory]::CreateDirectory($stagingRoot) | Out-Null }
    $cleanupStagingRoot = {
        try {
            if (Test-Path -LiteralPath $stagingRoot) {
                $children = @(Get-ChildItem -LiteralPath $stagingRoot -Force -ErrorAction SilentlyContinue)
                if ($children.Count -eq 0) {
                    Remove-Item -LiteralPath $stagingRoot -Force -ErrorAction SilentlyContinue
                }
            }
        } catch {}
    }

    # Pre-copy disk-space probe on the destination so we fail fast rather
    # than after a multi-GB partial transfer. Uses the UNC-aware helper.
    $srcSize = 0
    try {
        $srcSize = (Get-Item -LiteralPath $Source -ErrorAction Stop).Length
        $script:LastCopyFileRobocopyResult.TotalBytes = [long]$srcSize
        $script:LastCopyFileRobocopyResult.ProgressAvailable = ($srcSize -gt 0)
        $srcSizeGB = $srcSize / 1GB
        $dstFree   = Get-FreeSpaceGBAny $dstDir
        $reserveGB = $srcSizeGB + 0.5
        if (-not [string]::IsNullOrWhiteSpace([string]$Outsource) -and (Test-MediaPipelinePathIsEqualOrChild -Path $Destination -Root $Outsource)) {
            $reserveGB = [math]::Max($reserveGB, [double]$script:OutsourceMinFreeSpaceGB)
        }
        if ($dstFree -lt 0) {
            $reason = ("Unable to determine destination free space; refusing copy before mutation. Need {0:N2} GB+. Path: {1}" `
                -f $reserveGB, $dstDir)
            Write-Log $reason "ERROR"
            $script:LastCopyFileRobocopyResult.ReasonCode = 'OUTPUT_DESTINATION_SPACE_UNKNOWN'
            $script:LastCopyFileRobocopyResult.Reason = $reason
            $script:LastCopyFileRobocopyResult.DestinationFreeGB = -1
            $script:LastCopyFileRobocopyResult.RequiredGB = [double]$reserveGB
            & $cleanupStagingRoot
            return $false
        }
        if ($dstFree -ge 0 -and $dstFree -lt $reserveGB) {
            $reason = ("Destination has insufficient free space: {0:N2} GB free, need {1:N2} GB+. Path: {2}" `
                -f $dstFree, $reserveGB, $dstDir)
            Write-Log $reason "ERROR"
            $script:LastCopyFileRobocopyResult.ReasonCode = 'OUTPUT_DESTINATION_LOW_SPACE'
            $script:LastCopyFileRobocopyResult.Reason = $reason
            $script:LastCopyFileRobocopyResult.DestinationFreeGB = [double]$dstFree
            $script:LastCopyFileRobocopyResult.RequiredGB = [double]$reserveGB
            & $cleanupStagingRoot
            return $false
        }
    } catch {
        $reason = "Copy preflight failed for $Source -> $Destination : $_"
        Write-Log $reason "ERROR"
        $script:LastCopyFileRobocopyResult.ReasonCode = 'COPY_PREFLIGHT_FAILED'
        $script:LastCopyFileRobocopyResult.Reason = $reason
        $script:LastCopyFileRobocopyResult.DestinationFreeGB = -1
        $script:LastCopyFileRobocopyResult.RequiredGB = $null
        & $cleanupStagingRoot
        return $false
    }

    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        $script:LastCopyFileRobocopyResult.Attempts = $attempt
        if ($script:StopRequested -or (Test-Path -LiteralPath $StopFlag -ErrorAction SilentlyContinue)) {
            Write-Log "Copy canceled before attempt $attempt for $srcFile" "WARN"
            $script:StopRequested = $true
            $script:LastCopyFileRobocopyResult.ReasonCode = 'COPY_STOP_REQUESTED'
            $script:LastCopyFileRobocopyResult.Reason = "Copy canceled before attempt $attempt for $srcFile"
            & $cleanupStagingRoot
            return $false
        }

        $copyId = [guid]::NewGuid().ToString("N")
        $stagingDir = Join-Path $stagingRoot $copyId
        $partialPath = Join-Path $dstDir "$dstBase.mp-partial.$copyId"
        $backupPath  = Join-Path $dstDir "$dstBase.mp-backup.$copyId"
        $landedName  = Join-Path $stagingDir $srcFile

        [System.IO.Directory]::CreateDirectory($stagingDir) | Out-Null
        Write-Log "Copy attempt $attempt/$MaxRetries : $srcFile -> staging $copyId" "DEBUG"

        $rcArgs   = @($srcDir, $stagingDir, $srcFile) + $RobocopyFlags + @("/DCOPY:DA")
        $copyTelemetryCommand = Get-Command -Name Set-ProgressCopyTelemetry -ErrorAction SilentlyContinue
        $lastCopyProgressWriteAt = [ref]([datetime]::MinValue)
        $lastRobocopyProcessWriteBytes = [ref]$null
        $writeCopyProgress = {
            param([object]$BytesCopied, [bool]$Force)

            $bytes = 0L
            try { if ($null -ne $BytesCopied -and "$BytesCopied" -ne '') { $bytes = [long]$BytesCopied } } catch { $bytes = 0L }
            if ($bytes -lt 0) { $bytes = 0L }
            if ($srcSize -gt 0 -and $bytes -gt $srcSize) { $bytes = [long]$srcSize }

            $percent = $null
            if ($srcSize -gt 0) {
                $percent = [math]::Round((([double]$bytes / [double]$srcSize) * 100.0), 1)
            }
            $script:LastCopyFileRobocopyResult.BytesCopied = [long]$bytes
            $script:LastCopyFileRobocopyResult.TotalBytes = [long]$srcSize
            $script:LastCopyFileRobocopyResult.Percent = $percent
            $script:LastCopyFileRobocopyResult.ProgressAvailable = ($srcSize -gt 0)

            $now = Get-Date
            $shouldSave = [bool]$Force -or (($now - $lastCopyProgressWriteAt.Value).TotalSeconds -ge 1.0)
            if ($shouldSave -and $copyTelemetryCommand) {
                $lastCopyProgressWriteAt.Value = $now
                & $copyTelemetryCommand -Source $Source -Destination $Destination -BytesCopied $bytes -TotalBytes $srcSize -Percent $percent -Attempt $attempt -SyncStagePercent -SaveNow
            }
        }
        & $writeCopyProgress 0 $true
        $copyProgressPoll = {
            param($ElapsedSeconds, $Process)
            $landedBytes = 0L
            try {
                if (Test-Path -LiteralPath $landedName -PathType Leaf -ErrorAction SilentlyContinue) {
                    $landedBytes = [long](Get-Item -LiteralPath $landedName -ErrorAction Stop).Length
                }
            } catch {
                $landedBytes = 0L
            }
            $processWriteBytes = Get-RobocopyProcessWriteByteCount -Process $Process
            $bytes = Resolve-RobocopyActiveCopyProgressBytes `
                -LandedBytes $landedBytes `
                -TotalBytes $srcSize `
                -LastProgressBytes ([long]$script:LastCopyFileRobocopyResult.BytesCopied) `
                -CurrentProcessWriteBytes $processWriteBytes `
                -LastProcessWriteBytes $lastRobocopyProcessWriteBytes.Value
            if ($null -ne $processWriteBytes) {
                $lastRobocopyProcessWriteBytes.Value = [long]$processWriteBytes
            }
            & $writeCopyProgress $bytes $false
        }
        $rcResult = Invoke-NativeCommand -FilePath $robocopyPath -ArgumentList $rcArgs -TimeoutSeconds $script:RobocopyTimeoutSeconds -PollHandler $copyProgressPoll -PollMilliseconds 1000
        $finalCopyBytes = $script:LastCopyFileRobocopyResult.BytesCopied
        try {
            if (Test-Path -LiteralPath $landedName -PathType Leaf -ErrorAction SilentlyContinue) {
                $finalCopyBytes = [long](Get-Item -LiteralPath $landedName -ErrorAction Stop).Length
            }
        } catch {}
        & $writeCopyProgress $finalCopyBytes $true
        $rcOutput = @(($rcResult.Output + "`n" + $rcResult.Error) -split '\r?\n' | Where-Object { $_ -match '\S' })
        $rcExit   = [int]$rcResult.ExitCode
        if ($rcResult.Stopped) {
            Remove-Item -LiteralPath $stagingDir -Recurse -Force -ErrorAction SilentlyContinue
            & $cleanupStagingRoot
            return $false
        }
        if ($rcResult.TimedOut) {
            Write-Log "Robocopy timed out after $($script:RobocopyTimeoutSeconds)s — retrying with a fresh staging directory" "ERROR"
        }

        if ($DebugMode -and $rcOutput) {
            DebugLog ("  robocopy output:`n" + ($rcOutput -join "`n"))
        }

        $copyLanded = $false
        if ($rcExit -in @(0,1,3)) {
            try {
                $dstSize = (Get-Item -LiteralPath $landedName -ErrorAction Stop).Length
                if ($srcSize -eq $dstSize) {
                    $copyLanded = $true
                } else {
                    Write-Log "Size mismatch ($srcSize vs $dstSize) — retrying" "WARN"
                    Remove-Item -LiteralPath $landedName -Force -ErrorAction SilentlyContinue
                }
            } catch { Write-Log "Size verification failed: $_" "WARN" }
        } elseif ($rcExit -le 7) {
            Write-Log "Robocopy warning (exit $rcExit) — retrying" "WARN"
        } else {
            Write-Log "Robocopy hard failure (exit $rcExit)" "ERROR"
        }

        if ($copyLanded) {
            try {
                [System.IO.File]::Move($landedName, $partialPath, $true)
                if (Test-Path -LiteralPath $backupPath) {
                    Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
                }
                if (Test-Path -LiteralPath $Destination) {
                    [System.IO.File]::Replace($partialPath, $Destination, $backupPath, $true)
                    Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
                } else {
                    [System.IO.File]::Move($partialPath, $Destination, $true)
                }
                Write-Log "Copy succeeded (robocopy exit $rcExit)" "DEBUG"
                Remove-Item -LiteralPath $stagingDir -Recurse -Force -ErrorAction SilentlyContinue
                & $cleanupStagingRoot
                $script:LastCopyFileRobocopyResult.Ok = $true
                $script:LastCopyFileRobocopyResult.ReasonCode = 'COPY_SUCCEEDED'
                $script:LastCopyFileRobocopyResult.Reason = "Copy succeeded (robocopy exit $rcExit)"
                return $true
            } catch {
                Write-Log "Atomic-rename failed after successful copy: $_" "ERROR"
                $script:LastCopyFileRobocopyResult.ReasonCode = 'COPY_ATOMIC_RENAME_FAILED'
                $script:LastCopyFileRobocopyResult.Reason = [string]$_
                if (-not (Test-Path -LiteralPath $Destination) -and (Test-Path -LiteralPath $backupPath)) {
                    try { [System.IO.File]::Move($backupPath, $Destination, $true) }
                    catch { Write-Log "Failed to restore backup copy at $Destination : $_" "ERROR" }
                }
                # Partial may still exist — clean it up so the next attempt is fresh.
                Remove-Item -LiteralPath $partialPath -Force -ErrorAction SilentlyContinue
                Remove-Item -LiteralPath $backupPath  -Force -ErrorAction SilentlyContinue
                Remove-Item -LiteralPath $landedName  -Force -ErrorAction SilentlyContinue
            }
        }

        Remove-Item -LiteralPath $partialPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $backupPath  -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stagingDir  -Recurse -Force -ErrorAction SilentlyContinue
        & $cleanupStagingRoot
        if ($attempt -lt $MaxRetries) {
            if (-not (Start-StopAwareSleep 15)) { return $false }
        }
    }

    # Final cleanup — never leave staging or partial copy artifacts behind.
    try {
        Get-ChildItem -LiteralPath $stagingRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTime -lt (Get-Date).AddHours(-24) } |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    } catch {}
    & $cleanupStagingRoot
    Write-Log "Copy failed after $MaxRetries attempts: $srcFile" "ERROR"
    if ([string]::IsNullOrWhiteSpace([string]$script:LastCopyFileRobocopyResult.ReasonCode) -or [string]$script:LastCopyFileRobocopyResult.ReasonCode -eq 'COPY_PREFLIGHT_FAILED') {
        $script:LastCopyFileRobocopyResult.ReasonCode = 'COPY_FAILED'
        $script:LastCopyFileRobocopyResult.Reason = "Copy failed after $MaxRetries attempts: $srcFile"
    }
    return $false
}

# FIX#6: one-shot cleanup of stale partial files left over from an
# earlier crash. Called at startup before the main loop begins.
function Test-MediaPipelineStalePartialArtifactName {
    param([string]$Name)

    if ([string]::IsNullOrWhiteSpace($Name)) { return $false }
    $transactionIdPattern = '[0-9a-fA-F]{32}'
    if ($Name -match "\.mp-partial\.$transactionIdPattern$") { return $true }
    if ($Name -match "^\..+\.mp-publish-(partial|backup)\.$transactionIdPattern$") { return $true }
    return $false
}

function Test-MediaPipelineLocalEncodedCleanupRoot {
    param([string]$Root)

    if ([string]::IsNullOrWhiteSpace($Root)) {
        Write-Log "Skipping empty local encoded folder cleanup: LocalEncoded is not set" "WARN"
        return $false
    }
    if (-not (Get-Command -Name Test-MediaPipelinePathBoundarySafe -ErrorAction SilentlyContinue)) {
        Write-Log "Skipping empty local encoded folder cleanup: path boundary helper is unavailable" "ERROR"
        return $false
    }

    $localBaseVariable = Get-Variable -Name 'LocalBase' -Scope Script -ErrorAction SilentlyContinue
    $localBase = if ($localBaseVariable -and -not [string]::IsNullOrWhiteSpace([string]$localBaseVariable.Value)) {
        [string]$localBaseVariable.Value
    } else {
        ''
    }
    if ([string]::IsNullOrWhiteSpace($localBase)) {
        Write-Log "Skipping empty local encoded folder cleanup: LocalBase is not set" "ERROR"
        return $false
    }
    if (-not (Test-Path -LiteralPath $Root -PathType Container -ErrorAction SilentlyContinue)) {
        return $false
    }

    $rootBoundary = Test-MediaPipelinePathBoundarySafe -Path $Root -Root $localBase
    if (-not $rootBoundary.Ok) {
        Write-Log "Skipping empty local encoded folder cleanup for unsafe root ($($rootBoundary.ReasonCode)): $Root" "WARN"
        return $false
    }
    return $true
}

function Clear-EmptyLocalEncodedDirectories {
    param([string]$Root = ([string]$script:LocalEncoded))

    if (-not (Test-MediaPipelineLocalEncodedCleanupRoot -Root $Root)) {
        return [pscustomobject]@{ Scanned = 0; Removed = 0; SkippedUnsafe = 0; Errors = 0 }
    }

    $ageHours = [math]::Max(1, [int]$script:CleanupStaleAgeHours)
    $cutoff = (Get-Date).AddHours(-1 * $ageHours)
    $removed = 0
    $scanned = 0
    $skippedUnsafe = 0
    $errors = 0
    try {
        $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\','/')
        $directories = @(
            Invoke-RecursivePathScan -Path $Root -ItemType Directory -TimeoutSeconds $script:CleanupScanTimeoutSeconds -Label "empty local encoded folder cleanup" |
                ForEach-Object { [string]$_ } |
                Sort-Object { $_.Length } -Descending
        )
        foreach ($dir in $directories) {
            if ([string]::IsNullOrWhiteSpace($dir)) { continue }
            $scanned++
            $dirFull = [System.IO.Path]::GetFullPath($dir).TrimEnd('\','/')
            if ([string]::Equals($dirFull, $rootFull, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
            if ([System.IO.Path]::GetFileName($dirFull) -eq '.mediapipeline-staging') { continue }

            $candidateBoundary = Test-MediaPipelinePathBoundarySafe -Path $dir -Root $Root
            if (-not $candidateBoundary.Ok) {
                $skippedUnsafe++
                Write-Log "Skipping empty local encoded folder cleanup for unsafe path ($($candidateBoundary.ReasonCode)): $dir" "WARN"
                continue
            }

            try {
                $item = Get-Item -LiteralPath $dir -Force -ErrorAction Stop
                if ($item.LastWriteTime -ge $cutoff) { continue }
                $child = Get-ChildItem -LiteralPath $dir -Force -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($null -ne $child) { continue }
                Write-Log "Removing empty local encoded folder older than $ageHours hour(s): $dir" "WARN"
                Remove-Item -LiteralPath $dir -Force -ErrorAction Stop
                $removed++
            } catch {
                $errors++
                Write-Log "Empty local encoded folder cleanup failed for $dir : $_" "WARN"
            }
        }
    } catch {
        $errors++
        Write-Log "Empty local encoded folder cleanup failed for $Root : $_" "WARN"
    }

    if ($removed -gt 0) {
        Write-Log "Removed $removed empty local encoded folder(s) older than $ageHours hour(s)."
    } else {
        Write-Log "Empty local encoded folder cleanup found no eligible folders." "DEBUG"
    }
    return [pscustomobject]@{ Scanned = $scanned; Removed = $removed; SkippedUnsafe = $skippedUnsafe; Errors = $errors }
}

function Invoke-PeriodicLocalEncodedDirectoryCleanup {
    param([switch]$Force)

    $now = (Get-Date).ToUniversalTime()
    $intervalSeconds = 3600
    $last = Get-Variable -Name 'LastLocalEncodedDirectoryCleanupUtc' -Scope Script -ErrorAction SilentlyContinue
    if (-not $Force -and $last -and $last.Value -is [datetime]) {
        $elapsedSeconds = ($now - ([datetime]$last.Value).ToUniversalTime()).TotalSeconds
        if ($elapsedSeconds -lt $intervalSeconds) { return $null }
    }

    $script:LastLocalEncodedDirectoryCleanupUtc = $now
    return Clear-EmptyLocalEncodedDirectories
}

function Clear-StalePartialFiles {
    param([string[]]$Roots)
    $cutoff = (Get-Date).AddHours(-1 * [math]::Max(1, [int]$script:CleanupStaleAgeHours))
    foreach ($r in $Roots) {
        if ([string]::IsNullOrWhiteSpace($r)) { continue }
        if ((Test-IsUncPath $r) -and -not $script:CleanupRemoteStaging) {
            Write-Log "Skipping remote stale partial cleanup for $r (CleanupRemoteStaging=false)" "DEBUG"
            continue
        }
        if (-not (Test-IsUncPath $r) -and -not (Test-Path -LiteralPath $r)) { continue }
        $rootBoundary = Test-MediaPipelinePathBoundarySafe -Path $r -Root $r -AllowRootTarget
        if (-not $rootBoundary.Ok) {
            Write-Log "Skipping stale partial cleanup for unsafe root ($($rootBoundary.ReasonCode)): $r" "WARN"
            continue
        }
        try {
            Invoke-RecursivePathScan -Path $r -ItemType File -TimeoutSeconds $script:CleanupScanTimeoutSeconds -Label "stale partial cleanup" |
                Where-Object {
                    $name = [System.IO.Path]::GetFileName([string]$_)
                    if (Test-MediaPipelineStalePartialArtifactName -Name $name) {
                        try { ((Get-Item -LiteralPath ([string]$_) -ErrorAction Stop).LastWriteTime -lt $cutoff) }
                        catch { $false }
                    }
                    else { $false }
                } |
                ForEach-Object {
                    $candidateBoundary = Test-MediaPipelinePathBoundarySafe -Path ([string]$_) -Root $r
                    if (-not $candidateBoundary.Ok) {
                        Write-Log "Skipping stale partial cleanup for unsafe path ($($candidateBoundary.ReasonCode)): $_" "WARN"
                    } else {
                        Write-Log "Removing stale partial file: $_" "WARN"
                        Remove-Item -LiteralPath ([string]$_) -Force -ErrorAction SilentlyContinue
                    }
                }
            Invoke-RecursivePathScan -Path $r -ItemType Directory -TimeoutSeconds $script:CleanupScanTimeoutSeconds -Label "publish staging cleanup" |
                Where-Object {
                    $name = [System.IO.Path]::GetFileName([string]$_)
                    if ($name -ne '.mediapipeline-staging') { $false }
                    else {
                        try { ((Get-Item -LiteralPath ([string]$_) -ErrorAction Stop).LastWriteTime -lt $cutoff) }
                        catch { $false }
                    }
                } |
                ForEach-Object {
                    $candidateBoundary = Test-MediaPipelinePathBoundarySafe -Path ([string]$_) -Root $r
                    if (-not $candidateBoundary.Ok) {
                        Write-Log "Skipping publish staging cleanup for unsafe path ($($candidateBoundary.ReasonCode)): $_" "WARN"
                    } else {
                        Write-Log "Removing stale publish staging directory: $_" "WARN"
                        Remove-Item -LiteralPath ([string]$_) -Recurse -Force -ErrorAction SilentlyContinue
                    }
                }
        } catch { Write-Log "Partial-file cleanup failed for $r : $_" "WARN" }
    }
}
