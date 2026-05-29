# ==============================================================================
# Modules\ScratchCopy.ps1
# ==============================================================================
# Source-to-scratch copy helpers and scratch fingerprint safety.
#
# Dot-sourced from MediaPipeline_chatgpt.ps1. These helpers read runtime state
# from the main script scope at call time and preserve the existing source-file
# protection boundary: source media is copied to scratch, never mutated.
# ==============================================================================

# FIX#1: source-fingerprint helpers. The old Ensure-ScratchCopy reused any
# existing scratch file with the same sanitised name, so two different
# source files that sanitise to the same safe-name (e.g. "Episode 01.mkv"
# from two different shows, or a re-uploaded file) could cause the WRONG
# video to be encoded into the right output folder. We now write a
# <scratch>.srcinfo sidecar with the full source path, size, and mtime,
# and refuse to reuse the scratch unless all three match.

function Get-SourceFingerprint {
    param($SourceFile)
    return [ordered]@{
        full_path = $SourceFile.FullName
        size      = $SourceFile.Length
        mtime     = $SourceFile.LastWriteTimeUtc.ToString('o')
    }
}

function Get-FingerprintPath {
    param([string]$ScratchPath)
    return "$ScratchPath.srcinfo"
}

function Get-ScratchInputPath {
    param($SourceFile, [string]$SafeName)
    $identity = Get-SourceIdentityKey $SourceFile
    if ([string]::IsNullOrWhiteSpace($identity)) {
        $identity = [guid]::NewGuid().ToString('N')
    }
    $scratchDir = Join-Path $script:processingDir ("src_" + $identity.Substring(0, [math]::Min(16, $identity.Length)))
    return (Join-Path $scratchDir $SafeName)
}

function Remove-EmptyScratchContainer {
    param([string]$ScratchPath)
    if ([string]::IsNullOrWhiteSpace($ScratchPath)) { return }
    try {
        $parent = Split-Path $ScratchPath -Parent
        if ([string]::IsNullOrWhiteSpace($parent)) { return }
        $processingFull = [System.IO.Path]::GetFullPath($script:processingDir).TrimEnd('\','/')
        $parentFull = [System.IO.Path]::GetFullPath($parent).TrimEnd('\','/')
        if ($parentFull -eq $processingFull) { return }
        if (-not (Split-Path $parentFull -Leaf).StartsWith('src_')) { return }
        if ((Get-ChildItem -LiteralPath $parentFull -Force -ErrorAction SilentlyContinue | Select-Object -First 1) -eq $null) {
            Remove-Item -LiteralPath $parentFull -Force -ErrorAction SilentlyContinue
        }
    } catch {}
}

function Write-ScratchFingerprint {
    param([string]$ScratchPath, $SourceFile)
    try {
        $fp   = Get-SourceFingerprint $SourceFile
        $path = Get-FingerprintPath $ScratchPath
        $tmp  = "$path.$([guid]::NewGuid().ToString('N')).tmp"
        $fp | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $tmp -Encoding UTF8 -Force
        Move-Item -LiteralPath $tmp -Destination $path -Force
    } catch {
        Write-Log "Could not write scratch fingerprint at $ScratchPath : $_" "WARN"
        if ($tmp -and (Test-Path -LiteralPath $tmp -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
    }
}

function Test-ScratchFingerprintMatches {
    param([string]$ScratchPath, $SourceFile)
    $fpPath = Get-FingerprintPath $ScratchPath
    if (-not (Test-Path -LiteralPath $fpPath)) { return $false }
    try {
        $saved = Get-Content -LiteralPath $fpPath -Raw | ConvertFrom-Json
        if ([string]$saved.full_path -ne [string]$SourceFile.FullName) { return $false }
        if ([long]  $saved.size      -ne [long]  $SourceFile.Length)   { return $false }
        # ConvertFrom-Json materializes ISO timestamps as DateTime in PowerShell 7,
        # so normalize before comparing against the source file's round-trip value.
        $savedMtime = $saved.mtime
        if ($null -eq $savedMtime -and $saved.PSObject.Properties.Name -contains 'mtime_utc') {
            $savedMtime = $saved.mtime_utc
        }
        if ($savedMtime -is [datetime]) {
            $savedMtime = $savedMtime.ToUniversalTime().ToString('o')
        } else {
            $savedMtime = [string]$savedMtime
        }
        if ($savedMtime -ne $SourceFile.LastWriteTimeUtc.ToString('o')) { return $false }
        return $true
    } catch { return $false }
}

function Remove-ScratchFingerprint {
    param([string]$ScratchPath)
    $fpPath = Get-FingerprintPath $ScratchPath
    if (Test-Path -LiteralPath $fpPath) {
        Remove-Item -LiteralPath $fpPath -Force -ErrorAction SilentlyContinue
    }
}

function Ensure-ScratchCopy {
    param($SourceFile, [string]$SafeName)
    $localIn = Get-ScratchInputPath $SourceFile $SafeName
    if (Test-Path -LiteralPath $localIn) {
        # FIX#1: verify the existing scratch was made FROM THIS source file.
        # Different sources with the same sanitised name would otherwise
        # cause silent cross-contamination.
        if (-not (Test-ScratchFingerprintMatches $localIn $SourceFile)) {
            Write-Log "Existing scratch belongs to a different source - re-copying: $SafeName" "WARN"
            for ($i = 0; $i -lt 5; $i++) {
                try { Remove-Item -LiteralPath $localIn -Force -ErrorAction Stop; break }
                catch { Write-Log "Cannot delete mismatched scratch (attempt $($i+1)/5): $_" "WARN"; Start-Sleep 5 }
            }
            Remove-ScratchFingerprint $localIn
            Remove-EmptyScratchContainer $localIn
            if (Test-Path -LiteralPath $localIn) {
                Write-Log "Cannot delete mismatched scratch: $localIn" "ERROR"; return $null
            }
        }
        else {
            $existingIntegrity = Test-FileIntegrityDetailed -FilePath $localIn
            if (-not $existingIntegrity.Ok) {
                Write-Log "Existing scratch corrupt [$($existingIntegrity.ErrorCode)] - re-copying: $SafeName ($($existingIntegrity.Reason))" "WARN"
                for ($i = 0; $i -lt 5; $i++) {
                    try { Remove-Item -LiteralPath $localIn -Force -ErrorAction Stop; break }
                    catch { Write-Log "Cannot delete locked scratch (attempt $($i+1)/5): $_" "WARN"; Start-Sleep 5 }
                }
                Remove-ScratchFingerprint $localIn
                Remove-EmptyScratchContainer $localIn
                if (Test-Path -LiteralPath $localIn) { Write-Log "Cannot delete locked scratch: $localIn" "ERROR"; return $null }
            } else {
                # Fingerprint matched and integrity passed - reuse.
                return $localIn
            }
        }
    }
    Write-Log "COPY TO SCRATCH: $($SourceFile.Name) as $SafeName"
    Set-ProgressStage -Stage 'copy_to_scratch' -CopyState 'copying' -Percent $null -SaveNow
    if (-not (Copy-FileRobocopy $SourceFile.FullName $localIn)) { return $null }
    $scratchIntegrity = Test-FileIntegrityDetailed -FilePath $localIn
    if (-not $scratchIntegrity.Ok) {
        Write-Log "Scratch integrity failed [$($scratchIntegrity.ErrorCode)]: $SafeName - $($scratchIntegrity.Reason)" "ERROR"

        $sourceIntegrity = Test-FileIntegrityDetailed -FilePath $SourceFile.FullName
        if ($sourceIntegrity.Ok) {
            $classification = 'transient'
            $errorCode = 'SCRATCH_COPY_UNREADABLE'
            $reason = "Scratch integrity failed after verified copy: $($scratchIntegrity.Reason). Source integrity passed: $($sourceIntegrity.Reason)"
            $suggestedAction = 'Inspect the scratch disk, antivirus locks, and source-to-scratch copy path; the original source passed ffprobe after the failed scratch copy.'
            Write-Log "Source integrity passed after scratch failure: $($SourceFile.FullName)" "WARN"
        } else {
            $classification = 'permanent'
            $errorCode = Get-SourceIntegrityFailureCode -IntegrityResult $sourceIntegrity
            $reason = "Source integrity failed: $($sourceIntegrity.Reason). Scratch copy also failed: $($scratchIntegrity.Reason)"
            $suggestedAction = 'Redownload or replace the source; ffprobe cannot open the original file after a verified size copy.'
            Write-Log "Source integrity failed [$errorCode]: $($SourceFile.FullName) - $($sourceIntegrity.Reason)" "ERROR"
        }

        Remove-Item -LiteralPath $localIn -Force -ErrorAction SilentlyContinue
        Remove-ScratchFingerprint $localIn
        Remove-EmptyScratchContainer $localIn
        Register-SourceFailure -SourceFile $SourceFile -Classification $classification -Reason $reason -Stage 'scratch-integrity' -ErrorCode $errorCode -SuggestedAction $suggestedAction | Out-Null
        return $null
    }
    # Write the fingerprint AFTER integrity passes so a half-copied file
    # never gets accepted as a match next time.
    Write-ScratchFingerprint -ScratchPath $localIn -SourceFile $SourceFile
    Set-ProgressStage -Stage 'copy_to_scratch' -CopyState 'complete' -Percent 100 -SaveNow
    return $localIn
}
