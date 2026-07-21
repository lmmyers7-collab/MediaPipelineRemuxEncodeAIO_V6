# ==============================================================================
# Modules\ScratchCopy.ps1
# ==============================================================================
# Source-to-scratch copy helpers and scratch fingerprint safety.
#
# Dot-sourced from MediaPipeline.ps1. These helpers read runtime state
# from the main script scope at call time and preserve the existing source-file
# protection boundary: source media is copied to scratch, never mutated.
# ==============================================================================

# FIX#1 originally bound reuse to path/size/mtime. CPA-2026-07-19-003 proved
# that ordinary replacement tools can preserve all three while changing the
# bytes. The v2 sidecar below is therefore authoritative only when current
# source and scratch SHA-256 values are recomputed and equal. Legacy,
# malformed, missing, or unsupported evidence is invalidated by safe recopy.

function Get-ScratchCanonicalPath {
    param([Parameter(Mandatory)] [string] $Path)
    return [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
}

function Get-ScratchFileContentIdentity {
    param([Parameter(Mandatory)] [string] $Path)

    try {
        if ([string]::IsNullOrWhiteSpace($Path) -or
            -not (Test-Path -LiteralPath $Path -PathType Leaf -ErrorAction SilentlyContinue)) {
            return $null
        }

        $canonicalPath = Get-ScratchCanonicalPath -Path $Path
        $before = Get-Item -LiteralPath $canonicalPath -Force -ErrorAction Stop
        $beforeSize = [long]$before.Length
        $beforeMtime = $before.LastWriteTimeUtc.ToString('o')
        $sha256 = ((Get-FileHash -LiteralPath $canonicalPath -Algorithm SHA256 -ErrorAction Stop).Hash).ToLowerInvariant()
        $after = Get-Item -LiteralPath $canonicalPath -Force -ErrorAction Stop
        $afterMtime = $after.LastWriteTimeUtc.ToString('o')

        if ($sha256 -notmatch '^[0-9a-f]{64}$' -or
            $beforeSize -ne [long]$after.Length -or
            $beforeMtime -ne $afterMtime) {
            return $null
        }

        return [pscustomobject]@{
            Path = $canonicalPath
            Size = $beforeSize
            MtimeUtc = $beforeMtime
            Sha256 = $sha256
        }
    } catch {
        return $null
    }
}

function Test-ScratchContentIdentitySameBytes {
    param($Left, $Right)
    if ($null -eq $Left -or $null -eq $Right) { return $false }
    return (
        [long]$Left.Size -eq [long]$Right.Size -and
        [string]::Equals([string]$Left.Sha256, [string]$Right.Sha256, [System.StringComparison]::OrdinalIgnoreCase)
    )
}

function Test-ScratchSourceIdentityStable {
    param($Before, $After)
    if (-not (Test-ScratchContentIdentitySameBytes -Left $Before -Right $After)) { return $false }
    return (
        [string]::Equals([string]$Before.Path, [string]$After.Path, [System.StringComparison]::OrdinalIgnoreCase) -and
        [string]::Equals([string]$Before.MtimeUtc, [string]$After.MtimeUtc, [System.StringComparison]::Ordinal)
    )
}

function Get-SourceFingerprint {
    param(
        $SourceFile,
        [Parameter(Mandatory)] [string] $ScratchPath,
        $SourceIdentity = $null,
        $ScratchIdentity = $null
    )

    if ($null -eq $SourceIdentity) {
        $SourceIdentity = Get-ScratchFileContentIdentity -Path ([string]$SourceFile.FullName)
    }
    if ($null -eq $ScratchIdentity) {
        $ScratchIdentity = Get-ScratchFileContentIdentity -Path $ScratchPath
    }
    if ($null -eq $SourceIdentity -or $null -eq $ScratchIdentity) { return $null }

    return [ordered]@{
        schema_version  = 'scratch_source_identity.v2'
        hash_algorithm  = 'sha256'
        source_path     = [string]$SourceIdentity.Path
        source_size     = [long]$SourceIdentity.Size
        source_mtime_utc = [string]$SourceIdentity.MtimeUtc
        source_sha256   = [string]$SourceIdentity.Sha256
        scratch_size    = [long]$ScratchIdentity.Size
        scratch_sha256  = [string]$ScratchIdentity.Sha256
        verified_at_utc = [datetime]::UtcNow.ToString('o')
    }
}

function Get-FingerprintPath {
    param([string]$ScratchPath)
    return "$ScratchPath.srcinfo"
}

function Test-ScratchSafeLeafName {
    param([string]$SafeName)

    $name = ([string]$SafeName).Trim()
    if ([string]::IsNullOrWhiteSpace($name)) { return $false }
    if ($name -eq '.' -or $name -eq '..') { return $false }
    if ($name.IndexOfAny([char[]]@('\', '/')) -ge 0) { return $false }
    try {
        if ([System.IO.Path]::IsPathRooted($name)) { return $false }
        if ([System.IO.Path]::GetFileName($name) -ne $name) { return $false }
        foreach ($invalid in [System.IO.Path]::GetInvalidFileNameChars()) {
            if ($name.IndexOf($invalid) -ge 0) { return $false }
        }
    } catch {
        return $false
    }
    return $true
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

function Write-ScratchCleanupBoundaryLog {
    param([string]$Message, [string]$Level = 'WARN')

    if (Get-Command -Name Write-Log -ErrorAction SilentlyContinue) {
        Write-Log $Message $Level
    }
}

function Test-ScratchContainerCleanupBoundary {
    param([string]$ContainerPath)

    if ([string]::IsNullOrWhiteSpace($ContainerPath) -or [string]::IsNullOrWhiteSpace([string]$script:processingDir)) {
        return $false
    }
    if (-not (Get-Command -Name Test-MediaPipelinePathBoundarySafe -ErrorAction SilentlyContinue)) {
        Write-ScratchCleanupBoundaryLog 'Scratch container cleanup skipped: path boundary helper is unavailable.' 'ERROR'
        return $false
    }

    $localBaseVariable = Get-Variable -Name 'LocalBase' -Scope Script -ErrorAction SilentlyContinue
    $localBase = if ($localBaseVariable -and -not [string]::IsNullOrWhiteSpace([string]$localBaseVariable.Value)) {
        [string]$localBaseVariable.Value
    } else {
        ''
    }
    if ([string]::IsNullOrWhiteSpace($localBase)) {
        Write-ScratchCleanupBoundaryLog 'Scratch container cleanup skipped: LocalBase is not set.' 'ERROR'
        return $false
    }

    $processingBoundary = Test-MediaPipelinePathBoundarySafe -Path ([string]$script:processingDir) -Root $localBase
    if (-not $processingBoundary.Ok) {
        Write-ScratchCleanupBoundaryLog "Scratch container cleanup skipped: processingDir failed LocalBase boundary guard ($($processingBoundary.ReasonCode)): $($script:processingDir)" 'ERROR'
        return $false
    }

    $containerBoundary = Test-MediaPipelinePathBoundarySafe -Path $ContainerPath -Root ([string]$script:processingDir)
    if (-not $containerBoundary.Ok) {
        Write-ScratchCleanupBoundaryLog "Scratch container cleanup skipped: container failed processingDir boundary guard ($($containerBoundary.ReasonCode)): $ContainerPath" 'ERROR'
        return $false
    }
    return $true
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
        if (-not (Test-ScratchContainerCleanupBoundary -ContainerPath $parentFull)) { return }
        if ((Get-ChildItem -LiteralPath $parentFull -Force -ErrorAction SilentlyContinue | Select-Object -First 1) -eq $null) {
            Remove-Item -LiteralPath $parentFull -Force -ErrorAction SilentlyContinue
        }
    } catch {}
}

function Write-ScratchFingerprint {
    param(
        [Parameter(Mandatory)] [string] $ScratchPath,
        [Parameter(Mandatory)] $SourceFile,
        $SourceIdentity = $null,
        $ScratchIdentity = $null
    )

    $tmp = $null
    try {
        $fp = Get-SourceFingerprint `
            -SourceFile $SourceFile `
            -ScratchPath $ScratchPath `
            -SourceIdentity $SourceIdentity `
            -ScratchIdentity $ScratchIdentity
        if ($null -eq $fp) { return $false }
        $path = Get-FingerprintPath $ScratchPath
        $tmp  = "$path.$([guid]::NewGuid().ToString('N')).tmp"
        $fp | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $tmp -Encoding UTF8 -Force
        Move-Item -LiteralPath $tmp -Destination $path -Force
        return $true
    } catch {
        Write-Log "Could not write scratch fingerprint at $ScratchPath : $_" "WARN"
        if ($tmp -and (Test-Path -LiteralPath $tmp -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
        return $false
    }
}

function New-ScratchFingerprintValidationResult {
    param(
        [bool] $Ok,
        [string] $ReasonCode,
        $SourceIdentity = $null,
        $ScratchIdentity = $null
    )
    return [pscustomobject]@{
        Ok = $Ok
        ReasonCode = $ReasonCode
        SourceIdentity = $SourceIdentity
        ScratchIdentity = $ScratchIdentity
    }
}

function Get-ScratchFingerprintValidation {
    param([string]$ScratchPath, $SourceFile)

    $fpPath = Get-FingerprintPath $ScratchPath
    if (-not (Test-Path -LiteralPath $fpPath -PathType Leaf -ErrorAction SilentlyContinue)) {
        return New-ScratchFingerprintValidationResult -Ok $false -ReasonCode 'identity_evidence_missing'
    }
    try {
        $saved = Get-Content -LiteralPath $fpPath -Raw | ConvertFrom-Json
        if ($null -eq $saved -or $saved -is [System.Array]) {
            return New-ScratchFingerprintValidationResult -Ok $false -ReasonCode 'identity_evidence_malformed'
        }
        $propertyNames = @($saved.PSObject.Properties.Name)
        $required = @(
            'schema_version',
            'hash_algorithm',
            'source_path',
            'source_size',
            'source_mtime_utc',
            'source_sha256',
            'scratch_size',
            'scratch_sha256',
            'verified_at_utc'
        )
        foreach ($name in $required) {
            if ($propertyNames -notcontains $name) {
                return New-ScratchFingerprintValidationResult -Ok $false -ReasonCode 'identity_evidence_legacy_or_incomplete'
            }
        }

        if ([string]$saved.schema_version -ne 'scratch_source_identity.v2') {
            return New-ScratchFingerprintValidationResult -Ok $false -ReasonCode 'identity_schema_unsupported'
        }
        if (-not [string]::Equals(([string]$saved.hash_algorithm).Trim(), 'sha256', [System.StringComparison]::OrdinalIgnoreCase)) {
            return New-ScratchFingerprintValidationResult -Ok $false -ReasonCode 'hash_algorithm_unsupported'
        }
        if ([string]$saved.source_sha256 -notmatch '^[0-9a-fA-F]{64}$' -or
            [string]$saved.scratch_sha256 -notmatch '^[0-9a-fA-F]{64}$') {
            return New-ScratchFingerprintValidationResult -Ok $false -ReasonCode 'identity_digest_malformed'
        }

        $savedSourcePath = Get-ScratchCanonicalPath -Path ([string]$saved.source_path)
        $currentSourcePath = Get-ScratchCanonicalPath -Path ([string]$SourceFile.FullName)
        if (-not [string]::Equals($savedSourcePath, $currentSourcePath, [System.StringComparison]::OrdinalIgnoreCase)) {
            return New-ScratchFingerprintValidationResult -Ok $false -ReasonCode 'source_path_mismatch'
        }

        # Hash the source on both sides of the scratch hash. This prevents a
        # same-size/same-mtime source replacement during validation from
        # producing an apparently trustworthy reuse decision.
        $sourceBefore = Get-ScratchFileContentIdentity -Path $currentSourcePath
        $scratchIdentity = Get-ScratchFileContentIdentity -Path $ScratchPath
        $sourceAfter = Get-ScratchFileContentIdentity -Path $currentSourcePath
        if ($null -eq $sourceBefore -or $null -eq $scratchIdentity -or $null -eq $sourceAfter) {
            return New-ScratchFingerprintValidationResult -Ok $false -ReasonCode 'identity_recompute_failed'
        }
        if (-not (Test-ScratchSourceIdentityStable -Before $sourceBefore -After $sourceAfter)) {
            return New-ScratchFingerprintValidationResult -Ok $false -ReasonCode 'source_changed_during_validation'
        }
        if (-not (Test-ScratchContentIdentitySameBytes -Left $sourceAfter -Right $scratchIdentity)) {
            return New-ScratchFingerprintValidationResult -Ok $false -ReasonCode 'source_scratch_content_mismatch'
        }
        if ([long]$saved.source_size -ne [long]$sourceAfter.Size -or
            [long]$saved.scratch_size -ne [long]$scratchIdentity.Size -or
            -not [string]::Equals([string]$saved.source_sha256, [string]$sourceAfter.Sha256, [System.StringComparison]::OrdinalIgnoreCase) -or
            -not [string]::Equals([string]$saved.scratch_sha256, [string]$scratchIdentity.Sha256, [System.StringComparison]::OrdinalIgnoreCase)) {
            return New-ScratchFingerprintValidationResult -Ok $false -ReasonCode 'saved_identity_mismatch'
        }

        return New-ScratchFingerprintValidationResult `
            -Ok $true `
            -ReasonCode 'content_identity_match' `
            -SourceIdentity $sourceAfter `
            -ScratchIdentity $scratchIdentity
    } catch {
        return New-ScratchFingerprintValidationResult -Ok $false -ReasonCode 'identity_evidence_malformed'
    }
}

function Test-ScratchFingerprintMatches {
    param([string]$ScratchPath, $SourceFile)
    $validation = Get-ScratchFingerprintValidation -ScratchPath $ScratchPath -SourceFile $SourceFile
    $script:LastScratchFingerprintValidation = $validation
    return [bool]$validation.Ok
}

function Remove-ScratchFingerprint {
    param([string]$ScratchPath)
    $fpPath = Get-FingerprintPath $ScratchPath
    if (Test-Path -LiteralPath $fpPath) {
        Remove-Item -LiteralPath $fpPath -Force -ErrorAction SilentlyContinue
    }
}

function Set-MediaPipelineScratchCopyMonitorOutcome {
    param(
        [Parameter(Mandatory)]
        [ValidateSet('active','completed','skipped','blocked','failed')]
        [string] $State,
        [Parameter(Mandatory)] [string] $Detail,
        [string] $ReasonCode = ''
    )

    if (Get-Command -Name Set-MediaPipelineCurrentRunMonitorStage -ErrorAction SilentlyContinue) {
        Set-MediaPipelineCurrentRunMonitorStage `
            -StageId 'copy_to_scratch' `
            -State $State `
            -Detail $Detail `
            -ReasonCode $ReasonCode `
            -EvidenceSource 'scratch_copy' `
            -Indeterminate:($State -eq 'active') | Out-Null
    }
}

function Ensure-ScratchCopy {
    param($SourceFile, [string]$SafeName)
    if (-not (Test-ScratchSafeLeafName -SafeName $SafeName)) {
        Write-Log "Unsafe scratch safe name rejected: $SafeName" "ERROR"
        Set-MediaPipelineScratchCopyMonitorOutcome -State blocked -Detail 'Scratch copy rejected because the generated scratch leaf is unsafe.' -ReasonCode 'SCRATCH_SAFE_NAME_UNSAFE'
        return $null
    }

    $localIn = Get-ScratchInputPath $SourceFile $SafeName
    $scratchDir = Split-Path $localIn -Parent
    if ([string]::IsNullOrWhiteSpace($scratchDir)) {
        Write-Log "Scratch input path has no parent: $localIn" "ERROR"
        Set-MediaPipelineScratchCopyMonitorOutcome -State blocked -Detail 'Scratch copy rejected because the scratch input has no parent directory.' -ReasonCode 'SCRATCH_PATH_INVALID'
        return $null
    }
    if (-not (Get-Command -Name Test-MediaPipelinePathBoundarySafe -ErrorAction SilentlyContinue)) {
        Write-Log "Scratch copy rejected: path boundary helper is unavailable." "ERROR"
        Set-MediaPipelineScratchCopyMonitorOutcome -State blocked -Detail 'Scratch copy boundary validation is unavailable.' -ReasonCode 'SCRATCH_BOUNDARY_HELPER_UNAVAILABLE'
        return $null
    }
    if ([string]::IsNullOrWhiteSpace([string]$script:processingDir)) {
        Write-Log "Scratch copy rejected: processingDir is not set." "ERROR"
        Set-MediaPipelineScratchCopyMonitorOutcome -State blocked -Detail 'Scratch processing root is unavailable.' -ReasonCode 'SCRATCH_ROOT_UNAVAILABLE'
        return $null
    }
    $containerBoundary = Test-MediaPipelinePathBoundarySafe -Path $scratchDir -Root ([string]$script:processingDir) -AllowMissingLeaf
    if (-not [bool]$containerBoundary.Ok) {
        Write-Log "Scratch copy rejected: scratch container failed processingDir boundary guard ($($containerBoundary.ReasonCode)): $scratchDir" "ERROR"
        Set-MediaPipelineScratchCopyMonitorOutcome -State blocked -Detail 'Scratch container failed the processing-root boundary guard.' -ReasonCode ([string]$containerBoundary.ReasonCode)
        return $null
    }
    try {
        if (-not (Test-Path -LiteralPath $scratchDir -PathType Container -ErrorAction SilentlyContinue)) {
            New-Item -ItemType Directory -Path $scratchDir -Force -ErrorAction Stop | Out-Null
        }
    } catch {
        Write-Log "Scratch copy rejected: could not create scratch container $scratchDir : $_" "ERROR"
        Set-MediaPipelineScratchCopyMonitorOutcome -State failed -Detail 'Scratch container could not be created.' -ReasonCode 'SCRATCH_CONTAINER_CREATE_FAILED'
        return $null
    }
    $inputBoundary = Test-MediaPipelinePathBoundarySafe -Path $localIn -Root $scratchDir -AllowMissingLeaf
    if (-not [bool]$inputBoundary.Ok) {
        Write-Log "Scratch copy rejected: scratch input failed container boundary guard ($($inputBoundary.ReasonCode)): $localIn" "ERROR"
        Set-MediaPipelineScratchCopyMonitorOutcome -State blocked -Detail 'Scratch input failed the container boundary guard.' -ReasonCode ([string]$inputBoundary.ReasonCode)
        return $null
    }
    if (Get-Command -Name Set-MediaPipelineCurrentRunMonitorOutput -ErrorAction SilentlyContinue) {
        Set-MediaPipelineCurrentRunMonitorOutput -State active -ScratchPath $localIn -VerificationState not_started | Out-Null
    }

    if (Test-Path -LiteralPath $localIn) {
        # FIX#1: verify the existing scratch was made FROM THIS source file.
        # Different sources with the same sanitised name would otherwise
        # cause silent cross-contamination.
        if (-not (Test-ScratchFingerprintMatches $localIn $SourceFile)) {
            $identityReason = if ($script:LastScratchFingerprintValidation) {
                [string]$script:LastScratchFingerprintValidation.ReasonCode
            } else {
                'identity_untrusted'
            }
            Write-Log "Existing scratch identity is not trustworthy [$identityReason] - re-copying: $SafeName" "WARN"
            for ($i = 0; $i -lt 5; $i++) {
                try { Remove-Item -LiteralPath $localIn -Force -ErrorAction Stop; break }
                catch { Write-Log "Cannot delete mismatched scratch (attempt $($i+1)/5): $_" "WARN"; Start-Sleep 5 }
            }
            Remove-ScratchFingerprint $localIn
            Remove-EmptyScratchContainer $localIn
            if (Test-Path -LiteralPath $localIn) {
                Write-Log "Cannot delete mismatched scratch: $localIn" "ERROR"
                Set-MediaPipelineScratchCopyMonitorOutcome -State blocked -Detail 'A mismatched scratch copy is locked and cannot be safely replaced.' -ReasonCode 'SCRATCH_REPLACEMENT_BLOCKED'
                return $null
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
                if (Test-Path -LiteralPath $localIn) {
                    Write-Log "Cannot delete locked scratch: $localIn" "ERROR"
                    Set-MediaPipelineScratchCopyMonitorOutcome -State blocked -Detail 'A corrupt scratch copy is locked and cannot be safely replaced.' -ReasonCode 'SCRATCH_REPLACEMENT_BLOCKED'
                    return $null
                }
            } else {
                # Fingerprint matched and integrity passed - reuse.
                Set-ProgressStage -Stage 'copy_to_scratch' -Status 'Verified scratch copy reused' -CopyState 'reused' -Percent $null -SaveNow
                Set-MediaPipelineScratchCopyMonitorOutcome -State skipped -Detail 'An exact fingerprint-matched, integrity-verified scratch copy was reused.' -ReasonCode 'SCRATCH_COPY_REUSED'
                return $localIn
            }
        }
    }

    $sourceIdentityBeforeCopy = Get-ScratchFileContentIdentity -Path ([string]$SourceFile.FullName)
    if ($null -eq $sourceIdentityBeforeCopy) {
        Write-Log "Scratch copy rejected: source content identity could not be computed before copy: $($SourceFile.FullName)" "ERROR"
        Set-MediaPipelineScratchCopyMonitorOutcome -State failed -Detail 'The source SHA-256 identity could not be established before scratch copy.' -ReasonCode 'SCRATCH_COPY_FAILED'
        return $null
    }

    Write-Log "COPY TO SCRATCH: $($SourceFile.Name) as $SafeName"
    Set-MediaPipelineScratchCopyMonitorOutcome -State active -Detail 'Copying the accepted source to its backend-owned scratch path.'
    Set-ProgressStage -Stage 'copy_to_scratch' -CopyState 'copying' -Percent $null -SaveNow
    if (-not (Copy-FileRobocopy $SourceFile.FullName $localIn)) {
        $copyReasonCode = 'SCRATCH_COPY_FAILED'
        try {
            if ($script:LastCopyFileRobocopyResult -and
                -not [string]::IsNullOrWhiteSpace([string]$script:LastCopyFileRobocopyResult.ReasonCode)) {
                $copyReasonCode = [string]$script:LastCopyFileRobocopyResult.ReasonCode
            }
        } catch {}
        Set-MediaPipelineScratchCopyMonitorOutcome -State failed -Detail 'The backend source-to-scratch copy did not complete.' -ReasonCode $copyReasonCode
        return $null
    }
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
        Set-MediaPipelineScratchCopyMonitorOutcome -State failed -Detail $reason -ReasonCode $errorCode
        return $null
    }

    # Recompute exact content identity after the copy and after hashing the
    # landed scratch. A source that changes at any point in the simulated or
    # real copy window cannot authorize processing of uncertain scratch bytes.
    $scratchIdentity = Get-ScratchFileContentIdentity -Path $localIn
    $sourceIdentityAfterCopy = Get-ScratchFileContentIdentity -Path ([string]$SourceFile.FullName)
    $sourceStable = Test-ScratchSourceIdentityStable -Before $sourceIdentityBeforeCopy -After $sourceIdentityAfterCopy
    $contentMatches = Test-ScratchContentIdentitySameBytes -Left $sourceIdentityAfterCopy -Right $scratchIdentity
    if (-not $sourceStable -or -not $contentMatches) {
        $identityFailure = if (-not $sourceStable) {
            'The source content identity changed while it was being copied to scratch.'
        } else {
            'The landed scratch SHA-256 did not match the source SHA-256.'
        }
        Write-Log "$identityFailure Scratch copy discarded: $SafeName" "ERROR"
        Remove-Item -LiteralPath $localIn -Force -ErrorAction SilentlyContinue
        Remove-ScratchFingerprint $localIn
        Remove-EmptyScratchContainer $localIn
        Set-MediaPipelineScratchCopyMonitorOutcome -State failed -Detail $identityFailure -ReasonCode 'SCRATCH_COPY_FAILED'
        return $null
    }

    # Write content-bound evidence only after integrity and exact byte equality
    # pass. If the atomic evidence write fails, discard the scratch so a caller
    # can never process bytes lacking trustworthy provenance.
    $fingerprintWritten = Write-ScratchFingerprint `
        -ScratchPath $localIn `
        -SourceFile $SourceFile `
        -SourceIdentity $sourceIdentityAfterCopy `
        -ScratchIdentity $scratchIdentity
    if (-not $fingerprintWritten) {
        Write-Log "Scratch identity evidence could not be persisted; scratch copy discarded: $SafeName" "ERROR"
        Remove-Item -LiteralPath $localIn -Force -ErrorAction SilentlyContinue
        Remove-ScratchFingerprint $localIn
        Remove-EmptyScratchContainer $localIn
        Set-MediaPipelineScratchCopyMonitorOutcome -State failed -Detail 'Scratch identity evidence could not be persisted; the untrusted scratch copy was discarded.' -ReasonCode 'SCRATCH_COPY_FAILED'
        return $null
    }
    Set-ProgressStage -Stage 'copy_to_scratch' -CopyState 'complete' -Percent 100 -SaveNow
    Set-MediaPipelineScratchCopyMonitorOutcome -State completed -Detail 'Scratch copy completed with matching source/scratch SHA-256 identity evidence.'
    return $localIn
}
