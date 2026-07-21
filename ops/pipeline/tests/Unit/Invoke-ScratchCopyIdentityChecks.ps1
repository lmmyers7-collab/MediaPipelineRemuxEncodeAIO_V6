$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..'))
$scratchCopyPath = Join-Path $repoRoot 'ops\pipeline\engine\storage\scratch_copy.ps1'

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) {
        throw "$Message (expected='$Expected', actual='$Actual')"
    }
}

function Get-TestSha256 {
    param([Parameter(Mandatory)] [string] $Path)
    return ((Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash).ToLowerInvariant()
}

function Set-TestContent {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string] $Content,
        [datetime] $LastWriteTimeUtc = [datetime]::Parse('2026-01-02T03:04:05Z').ToUniversalTime()
    )

    $parent = Split-Path -Path $Path -Parent
    if (-not (Test-Path -LiteralPath $parent -PathType Container -ErrorAction SilentlyContinue)) {
        [System.IO.Directory]::CreateDirectory($parent) | Out-Null
    }
    [System.IO.File]::WriteAllBytes($Path, [System.Text.Encoding]::ASCII.GetBytes($Content))
    [System.IO.File]::SetLastWriteTimeUtc($Path, $LastWriteTimeUtc)
}

function Get-TestCanonicalPath {
    param([Parameter(Mandatory)] [string] $Path)
    return [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
}

function Test-MediaPipelinePathBoundarySafe {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string] $Root,
        [switch] $AllowMissingLeaf
    )

    try {
        $pathFull = Get-TestCanonicalPath -Path $Path
        $rootFull = Get-TestCanonicalPath -Path $Root
        $prefix = $rootFull + [System.IO.Path]::DirectorySeparatorChar
        $ok = (
            [string]::Equals($pathFull, $rootFull, [System.StringComparison]::OrdinalIgnoreCase) -or
            $pathFull.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
        )
        return [pscustomobject]@{
            Ok = $ok
            ReasonCode = if ($ok) { 'OK' } else { 'PATH_OUTSIDE_ROOT' }
        }
    } catch {
        return [pscustomobject]@{ Ok = $false; ReasonCode = 'PATH_INVALID' }
    }
}

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
    $script:TestLog += ,([pscustomobject]@{ Level = $Level; Message = $Message })
}

function Set-ProgressStage {
    param(
        [string] $Stage,
        [string] $Status,
        [string] $CopyState,
        $Percent,
        [switch] $SaveNow
    )
}

function Set-MediaPipelineCurrentRunMonitorOutput {
    param([string] $State, [string] $ScratchPath, [string] $VerificationState)
}

function Set-MediaPipelineCurrentRunMonitorStage {
    param(
        [string] $StageId,
        [string] $State,
        [string] $Detail,
        [string] $ReasonCode,
        [string] $EvidenceSource,
        [switch] $Indeterminate
    )
    $script:MonitorStages += ,([pscustomobject]@{
        StageId = $StageId
        State = $State
        Detail = $Detail
        ReasonCode = $ReasonCode
        EvidenceSource = $EvidenceSource
    })
}

function Get-SourceIdentityKey {
    param($SourceFile)
    return [string]$script:ForcedScratchIdentity
}

function Copy-FileRobocopy {
    param([string] $Source, [string] $Destination, [int] $MaxRetries = 3)

    $script:CopyCount++
    $parent = Split-Path -Path $Destination -Parent
    [System.IO.Directory]::CreateDirectory($parent) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Force -ErrorAction Stop
    if ($script:CopyMutationAction) {
        & $script:CopyMutationAction
    }
    $script:LastCopyFileRobocopyResult = [pscustomobject]@{
        Ok = $true
        ReasonCode = 'COPY_SUCCEEDED'
        Reason = 'synthetic copy completed'
    }
    return $true
}

function Test-FileIntegrityDetailed {
    param([string] $FilePath)
    return [pscustomobject]@{
        Ok = (Test-Path -LiteralPath $FilePath -PathType Leaf -ErrorAction SilentlyContinue)
        ErrorCode = 'OK'
        Reason = 'synthetic integrity boundary intentionally accepts any existing tiny file'
    }
}

function Get-SourceIntegrityFailureCode {
    param($IntegrityResult)
    return 'SOURCE_CORRUPT'
}

function Register-SourceFailure {
    param($SourceFile, [string] $Classification, [string] $Reason, [string] $Stage, [string] $ErrorCode, [string] $SuggestedAction)
    return [pscustomobject]@{ Ok = $true }
}

# Locked-stale coverage must not spend 25 seconds in the production retry delay.
function Start-Sleep {
    param([int] $Seconds, [int] $Milliseconds)
}

. $scratchCopyPath

function Reset-CaseState {
    param([Parameter(Mandatory)] $Environment)

    $script:LocalBase = $Environment.LocalBase
    $script:processingDir = $Environment.ProcessingRoot
    $script:ForcedScratchIdentity = 'cpascratchidentityfixture'
    $script:CopyCount = 0
    $script:CopyMutationAction = $null
    $script:ExpectedExternalSourceHashes = [ordered]@{}
    $script:LastSourceProof = $null
    $script:TestLog = @()
    $script:MonitorStages = @()
}

function New-CaseEnvironment {
    param(
        [Parameter(Mandatory)] [string] $CampaignRoot,
        [Parameter(Mandatory)] [string] $Name
    )

    $safeName = ($Name -replace '[^a-zA-Z0-9_-]', '_')
    $caseRoot = Join-Path $CampaignRoot $safeName
    $sourceRoot = Join-Path $caseRoot 'source'
    $scratchRoot = Join-Path $caseRoot 'scratch'
    $localBase = Join-Path $scratchRoot 'LocalBase'
    $processingRoot = Join-Path (Join-Path $localBase 'Incoming') 'Processing'
    [System.IO.Directory]::CreateDirectory($sourceRoot) | Out-Null
    [System.IO.Directory]::CreateDirectory($processingRoot) | Out-Null
    return [pscustomobject]@{
        CaseRoot = $caseRoot
        SourceRoot = $sourceRoot
        ScratchRoot = $scratchRoot
        LocalBase = $localBase
        ProcessingRoot = $processingRoot
    }
}

function Write-LegacyFingerprint {
    param(
        [Parameter(Mandatory)] [string] $ScratchPath,
        [Parameter(Mandatory)] $SourceFile
    )

    [ordered]@{
        full_path = [string]$SourceFile.FullName
        size = [long]$SourceFile.Length
        mtime = $SourceFile.LastWriteTimeUtc.ToString('o')
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Get-FingerprintPath $ScratchPath) -Encoding UTF8
}

function Write-ClaimedV2Fingerprint {
    param(
        [Parameter(Mandatory)] [string] $ScratchPath,
        [Parameter(Mandatory)] $SourceFile,
        [string] $SchemaVersion = 'scratch_source_identity.v2',
        [string] $HashAlgorithm = 'sha256',
        [string] $SourceHash = '',
        [string] $ScratchHash = ''
    )

    if ([string]::IsNullOrWhiteSpace($SourceHash)) { $SourceHash = Get-TestSha256 -Path $SourceFile.FullName }
    if ([string]::IsNullOrWhiteSpace($ScratchHash)) { $ScratchHash = Get-TestSha256 -Path $ScratchPath }
    [ordered]@{
        schema_version = $SchemaVersion
        hash_algorithm = $HashAlgorithm
        source_path = Get-TestCanonicalPath -Path $SourceFile.FullName
        source_size = [long]$SourceFile.Length
        source_mtime_utc = $SourceFile.LastWriteTimeUtc.ToString('o')
        source_sha256 = $SourceHash
        scratch_size = [long](Get-Item -LiteralPath $ScratchPath).Length
        scratch_sha256 = $ScratchHash
        verified_at_utc = '2026-01-02T03:04:05.0000000Z'
        # Legacy fields are included deliberately: an unsupported v2 record
        # must not be accepted by falling back to metadata-only parsing.
        full_path = [string]$SourceFile.FullName
        size = [long]$SourceFile.Length
        mtime = $SourceFile.LastWriteTimeUtc.ToString('o')
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Get-FingerprintPath $ScratchPath) -Encoding UTF8
}

function Assert-TrustedFingerprint {
    param(
        [Parameter(Mandatory)] [string] $ScratchPath,
        [Parameter(Mandatory)] [string] $SourcePath
    )

    $fingerprintPath = Get-FingerprintPath $ScratchPath
    Assert-True (Test-Path -LiteralPath $fingerprintPath -PathType Leaf) 'Trusted scratch identity evidence was not written.'
    $saved = Get-Content -LiteralPath $fingerprintPath -Raw | ConvertFrom-Json -ErrorAction Stop
    Assert-Equal ([string]$saved.schema_version) 'scratch_source_identity.v2' 'Scratch evidence schema must invalidate legacy metadata-only records.'
    Assert-Equal (([string]$saved.hash_algorithm).ToLowerInvariant()) 'sha256' 'Scratch evidence must declare SHA-256.'
    Assert-True (([string]$saved.source_sha256) -match '^[0-9a-f]{64}$') 'Scratch evidence source_sha256 must be a lowercase SHA-256 digest.'
    Assert-True (([string]$saved.scratch_sha256) -match '^[0-9a-f]{64}$') 'Scratch evidence scratch_sha256 must be a lowercase SHA-256 digest.'
    $sourceHash = Get-TestSha256 -Path $SourcePath
    $scratchHash = Get-TestSha256 -Path $ScratchPath
    Assert-Equal ([string]$saved.source_sha256) $sourceHash 'Saved source SHA-256 must match the current source bytes.'
    Assert-Equal ([string]$saved.scratch_sha256) $scratchHash 'Saved scratch SHA-256 must match the landed scratch bytes.'
    Assert-Equal $scratchHash $sourceHash 'Trusted scratch bytes must equal source bytes.'
    Assert-True ([string]::Equals(
        (Get-TestCanonicalPath -Path ([string]$saved.source_path)),
        (Get-TestCanonicalPath -Path $SourcePath),
        [System.StringComparison]::OrdinalIgnoreCase
    )) 'Scratch evidence source path must be the canonical current source path.'
    return $saved
}

function Invoke-ProtectedPipelineAction {
    param(
        [Parameter(Mandatory)] [string[]] $SourcePaths,
        [Parameter(Mandatory)] [scriptblock] $Action
    )

    $before = [ordered]@{}
    foreach ($path in $SourcePaths) {
        Assert-True (Test-Path -LiteralPath $path -PathType Leaf) "Source fixture missing before pipeline action: $path"
        $before[(Get-TestCanonicalPath -Path $path)] = Get-TestSha256 -Path $path
    }

    $result = & $Action

    $after = [ordered]@{}
    foreach ($path in $SourcePaths) {
        $canonical = Get-TestCanonicalPath -Path $path
        Assert-True (Test-Path -LiteralPath $path -PathType Leaf) "Pipeline removed or renamed source fixture: $path"
        $after[$canonical] = Get-TestSha256 -Path $path
        if ($script:ExpectedExternalSourceHashes.Contains($canonical)) {
            Assert-Equal $after[$canonical] $script:ExpectedExternalSourceHashes[$canonical] "Pipeline changed source after the deliberate external adversary mutation: $path"
        } else {
            Assert-Equal $after[$canonical] $before[$canonical] "Pipeline mutated source fixture: $path"
        }
    }

    $proof = [pscustomobject]@{
        Result = $result
        SourceHashesBefore = $before
        SourceHashesAfter = $after
    }
    $script:LastSourceProof = $proof
    return $proof
}

$caseRows = [System.Collections.Generic.List[object]]::new()
$failures = [System.Collections.Generic.List[string]]::new()
$campaignRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-cpa-scratch-identity-' + [guid]::NewGuid().ToString('N'))
[System.IO.Directory]::CreateDirectory($campaignRoot) | Out-Null

function Invoke-MatrixCase {
    param(
        [Parameter(Mandatory)] [string] $Name,
        [Parameter(Mandatory)] [string] $ExpectedDisposition,
        [Parameter(Mandatory)] [scriptblock] $Body
    )

    $environment = New-CaseEnvironment -CampaignRoot $campaignRoot -Name $Name
    Reset-CaseState -Environment $environment
    $started = Get-Date
    $details = $null
    $failure = ''
    try {
        $details = & $Body $environment
    } catch {
        $failure = [string]$_.Exception.Message
        $failures.Add("$Name :: $failure")
    }

    $proof = if ($details -and $details.Proof) { $details.Proof } else { $script:LastSourceProof }
    $sourceBefore = if ($proof) { $proof.SourceHashesBefore } else { [ordered]@{} }
    $sourceAfter = if ($proof) { $proof.SourceHashesAfter } else { [ordered]@{} }
    $caseRows.Add([pscustomobject]@{
        case = $Name
        expected_disposition = $ExpectedDisposition
        observed = if ([string]::IsNullOrWhiteSpace($failure)) { [string]$details.Observed } else { 'assertion_failed' }
        passed = [string]::IsNullOrWhiteSpace($failure)
        copy_count = [int]$script:CopyCount
        source_hashes_before = $sourceBefore
        source_hashes_after = $sourceAfter
        scratch_hash_after = if ($details) { [string]$details.ScratchHashAfter } else { '' }
        reason_code = if ($details) { [string]$details.ReasonCode } else { '' }
        failure = $failure
        elapsed_ms = [math]::Round(((Get-Date) - $started).TotalMilliseconds, 1)
    })
}

try {
    Invoke-MatrixCase -Name 'exact_content_match_successful_reuse' -ExpectedDisposition 'reuse' -Body {
        param($env)
        $sourcePath = Join-Path $env.SourceRoot 'movie.mkv'
        Set-TestContent -Path $sourcePath -Content 'MATCH-0001'
        $source = Get-Item -LiteralPath $sourcePath
        $scratchPath = Get-ScratchInputPath -SourceFile $source -SafeName 'movie.mkv'
        $proof = Invoke-ProtectedPipelineAction -SourcePaths @($sourcePath) -Action {
            $first = Ensure-ScratchCopy -SourceFile $source -SafeName 'movie.mkv'
            Assert-Equal $first $scratchPath 'Initial exact-content copy did not land at the reserved scratch path.'
            Assert-TrustedFingerprint -ScratchPath $scratchPath -SourcePath $sourcePath | Out-Null
            $script:CopyCount = 0
            $second = Ensure-ScratchCopy -SourceFile (Get-Item -LiteralPath $sourcePath) -SafeName 'movie.mkv'
            Assert-Equal $second $scratchPath 'Unchanged content should reuse the verified scratch path.'
            Assert-Equal $script:CopyCount 0 'Unchanged content should not be copied again.'
            return $second
        }
        return [pscustomobject]@{ Proof = $proof; Observed = 'reused'; ScratchHashAfter = Get-TestSha256 $scratchPath; ReasonCode = 'SCRATCH_COPY_REUSED' }
    }

    Invoke-MatrixCase -Name 'different_content_same_name_length_timestamp' -ExpectedDisposition 'safe_recopy' -Body {
        param($env)
        $sourcePath = Join-Path $env.SourceRoot 'movie.mkv'
        $mtime = [datetime]::Parse('2026-01-02T03:04:05Z').ToUniversalTime()
        Set-TestContent -Path $sourcePath -Content 'AAAA-0001' -LastWriteTimeUtc $mtime
        $source = Get-Item -LiteralPath $sourcePath
        $scratchPath = Ensure-ScratchCopy -SourceFile $source -SafeName 'movie.mkv'
        $oldScratchHash = Get-TestSha256 $scratchPath
        Set-TestContent -Path $sourcePath -Content 'BBBB-0001' -LastWriteTimeUtc $mtime
        $sourceHash = Get-TestSha256 $sourcePath
        Assert-True ($sourceHash -ne $oldScratchHash) 'Adversarial replacement fixture did not change content.'
        $script:CopyCount = 0
        $proof = Invoke-ProtectedPipelineAction -SourcePaths @($sourcePath) -Action {
            return Ensure-ScratchCopy -SourceFile (Get-Item -LiteralPath $sourcePath) -SafeName 'movie.mkv'
        }
        Assert-Equal $script:CopyCount 1 'Same-metadata content replacement must force one safe recopy.'
        Assert-Equal (Get-TestSha256 $scratchPath) $sourceHash 'Safe recopy did not replace stale scratch bytes.'
        Assert-TrustedFingerprint -ScratchPath $scratchPath -SourcePath $sourcePath | Out-Null
        return [pscustomobject]@{ Proof = $proof; Observed = 'recopied'; ScratchHashAfter = Get-TestSha256 $scratchPath; ReasonCode = 'content_mismatch' }
    }

    Invoke-MatrixCase -Name 'source_replaced_after_discovery_before_copy' -ExpectedDisposition 'safe_recopy_current_bytes' -Body {
        param($env)
        $sourcePath = Join-Path $env.SourceRoot 'discovered.mkv'
        $mtime = [datetime]::Parse('2026-01-02T03:04:05Z').ToUniversalTime()
        Set-TestContent -Path $sourcePath -Content 'DISC-OLD' -LastWriteTimeUtc $mtime
        $discovered = Get-Item -LiteralPath $sourcePath
        $scratchPath = Ensure-ScratchCopy -SourceFile $discovered -SafeName 'discovered.mkv'
        Set-TestContent -Path $sourcePath -Content 'DISC-NEW' -LastWriteTimeUtc $mtime
        $currentHash = Get-TestSha256 $sourcePath
        $script:CopyCount = 0
        $proof = Invoke-ProtectedPipelineAction -SourcePaths @($sourcePath) -Action {
            return Ensure-ScratchCopy -SourceFile $discovered -SafeName 'discovered.mkv'
        }
        Assert-Equal $script:CopyCount 1 'A stale discovery object must not authorize stale scratch reuse.'
        Assert-Equal (Get-TestSha256 $scratchPath) $currentHash 'Copy did not bind to bytes present at copy time.'
        Assert-TrustedFingerprint -ScratchPath $scratchPath -SourcePath $sourcePath | Out-Null
        return [pscustomobject]@{ Proof = $proof; Observed = 'recopied_current_source'; ScratchHashAfter = Get-TestSha256 $scratchPath; ReasonCode = 'discovery_identity_refreshed' }
    }

    Invoke-MatrixCase -Name 'source_changed_during_simulated_copy' -ExpectedDisposition 'fail_closed_discard_scratch' -Body {
        param($env)
        $sourcePath = Join-Path $env.SourceRoot 'changing.mkv'
        $mtime = [datetime]::Parse('2026-01-02T03:04:05Z').ToUniversalTime()
        Set-TestContent -Path $sourcePath -Content 'COPY-OLD' -LastWriteTimeUtc $mtime
        $source = Get-Item -LiteralPath $sourcePath
        $scratchPath = Get-ScratchInputPath -SourceFile $source -SafeName 'changing.mkv'
        $capturedPath = $sourcePath
        $capturedMtime = $mtime
        $expectedExternalHashes = $script:ExpectedExternalSourceHashes
        $script:CopyMutationAction = {
            Set-TestContent -Path $capturedPath -Content 'COPY-NEW' -LastWriteTimeUtc $capturedMtime
            $canonical = Get-TestCanonicalPath -Path $capturedPath
            $expectedExternalHashes[$canonical] = Get-TestSha256 -Path $capturedPath
        }.GetNewClosure()
        $proof = Invoke-ProtectedPipelineAction -SourcePaths @($sourcePath) -Action {
            return Ensure-ScratchCopy -SourceFile $source -SafeName 'changing.mkv'
        }
        Assert-True ($null -eq $proof.Result) 'Source change during copy must fail closed.'
        Assert-True (-not (Test-Path -LiteralPath $scratchPath -PathType Leaf -ErrorAction SilentlyContinue)) 'Uncertain scratch bytes must be discarded after a during-copy source change.'
        Assert-True (-not (Test-Path -LiteralPath (Get-FingerprintPath $scratchPath) -PathType Leaf -ErrorAction SilentlyContinue)) 'Identity evidence must not survive a during-copy mismatch.'
        $lastStage = @($script:MonitorStages | Where-Object { $_.StageId -eq 'copy_to_scratch' }) | Select-Object -Last 1
        Assert-Equal ([string]$lastStage.State) 'failed' 'During-copy source change must leave a failed copy stage.'
        return [pscustomobject]@{ Proof = $proof; Observed = 'failed_closed'; ScratchHashAfter = ''; ReasonCode = [string]$lastStage.ReasonCode }
    }

    Invoke-MatrixCase -Name 'truncated_scratch_copy' -ExpectedDisposition 'safe_recopy' -Body {
        param($env)
        $sourcePath = Join-Path $env.SourceRoot 'truncated.mkv'
        Set-TestContent -Path $sourcePath -Content 'TRUNCATE-FULL'
        $source = Get-Item -LiteralPath $sourcePath
        $scratchPath = Ensure-ScratchCopy -SourceFile $source -SafeName 'truncated.mkv'
        Set-TestContent -Path $scratchPath -Content 'TRUNC'
        $script:CopyCount = 0
        $proof = Invoke-ProtectedPipelineAction -SourcePaths @($sourcePath) -Action {
            return Ensure-ScratchCopy -SourceFile (Get-Item -LiteralPath $sourcePath) -SafeName 'truncated.mkv'
        }
        Assert-Equal $script:CopyCount 1 'Truncated scratch must be recopied even when the structural integrity stub accepts it.'
        Assert-Equal (Get-TestSha256 $scratchPath) (Get-TestSha256 $sourcePath) 'Truncated scratch was not replaced with exact source bytes.'
        Assert-TrustedFingerprint -ScratchPath $scratchPath -SourcePath $sourcePath | Out-Null
        return [pscustomobject]@{ Proof = $proof; Observed = 'recopied'; ScratchHashAfter = Get-TestSha256 $scratchPath; ReasonCode = 'scratch_hash_mismatch' }
    }

    Invoke-MatrixCase -Name 'stale_metadata_claiming_content_match' -ExpectedDisposition 'safe_recopy' -Body {
        param($env)
        $sourcePath = Join-Path $env.SourceRoot 'forged.mkv'
        Set-TestContent -Path $sourcePath -Content 'SOURCE-01'
        $source = Get-Item -LiteralPath $sourcePath
        $scratchPath = Get-ScratchInputPath -SourceFile $source -SafeName 'forged.mkv'
        Set-TestContent -Path $scratchPath -Content 'STALE--01' -LastWriteTimeUtc $source.LastWriteTimeUtc
        $sourceHash = Get-TestSha256 $sourcePath
        Write-ClaimedV2Fingerprint -ScratchPath $scratchPath -SourceFile $source -SourceHash $sourceHash -ScratchHash $sourceHash
        $proof = Invoke-ProtectedPipelineAction -SourcePaths @($sourcePath) -Action {
            return Ensure-ScratchCopy -SourceFile $source -SafeName 'forged.mkv'
        }
        Assert-Equal $script:CopyCount 1 'Saved hash claims must be recomputed, not trusted.'
        Assert-Equal (Get-TestSha256 $scratchPath) $sourceHash 'Forged stale scratch was silently retained.'
        Assert-TrustedFingerprint -ScratchPath $scratchPath -SourcePath $sourcePath | Out-Null
        return [pscustomobject]@{ Proof = $proof; Observed = 'recopied'; ScratchHashAfter = Get-TestSha256 $scratchPath; ReasonCode = 'saved_hash_claim_disproved' }
    }

    Invoke-MatrixCase -Name 'missing_hash_evidence' -ExpectedDisposition 'safe_recopy' -Body {
        param($env)
        $sourcePath = Join-Path $env.SourceRoot 'missing.mkv'
        Set-TestContent -Path $sourcePath -Content 'SOURCE-02'
        $source = Get-Item -LiteralPath $sourcePath
        $scratchPath = Get-ScratchInputPath -SourceFile $source -SafeName 'missing.mkv'
        Set-TestContent -Path $scratchPath -Content 'STALE--02' -LastWriteTimeUtc $source.LastWriteTimeUtc
        $proof = Invoke-ProtectedPipelineAction -SourcePaths @($sourcePath) -Action {
            return Ensure-ScratchCopy -SourceFile $source -SafeName 'missing.mkv'
        }
        Assert-Equal $script:CopyCount 1 'Scratch without identity evidence must be recopied.'
        Assert-TrustedFingerprint -ScratchPath $scratchPath -SourcePath $sourcePath | Out-Null
        return [pscustomobject]@{ Proof = $proof; Observed = 'recopied'; ScratchHashAfter = Get-TestSha256 $scratchPath; ReasonCode = 'identity_evidence_missing' }
    }

    Invoke-MatrixCase -Name 'malformed_hash_evidence' -ExpectedDisposition 'safe_recopy' -Body {
        param($env)
        $sourcePath = Join-Path $env.SourceRoot 'malformed.mkv'
        Set-TestContent -Path $sourcePath -Content 'SOURCE-03'
        $source = Get-Item -LiteralPath $sourcePath
        $scratchPath = Get-ScratchInputPath -SourceFile $source -SafeName 'malformed.mkv'
        Set-TestContent -Path $scratchPath -Content 'STALE--03' -LastWriteTimeUtc $source.LastWriteTimeUtc
        [System.IO.File]::WriteAllText((Get-FingerprintPath $scratchPath), '{ definitely-not-json')
        $proof = Invoke-ProtectedPipelineAction -SourcePaths @($sourcePath) -Action {
            return Ensure-ScratchCopy -SourceFile $source -SafeName 'malformed.mkv'
        }
        Assert-Equal $script:CopyCount 1 'Malformed identity evidence must be invalidated and recopied.'
        Assert-TrustedFingerprint -ScratchPath $scratchPath -SourcePath $sourcePath | Out-Null
        return [pscustomobject]@{ Proof = $proof; Observed = 'recopied'; ScratchHashAfter = Get-TestSha256 $scratchPath; ReasonCode = 'identity_evidence_malformed' }
    }

    Invoke-MatrixCase -Name 'unsupported_hash_evidence' -ExpectedDisposition 'safe_recopy' -Body {
        param($env)
        $sourcePath = Join-Path $env.SourceRoot 'unsupported.mkv'
        Set-TestContent -Path $sourcePath -Content 'SOURCE-04'
        $source = Get-Item -LiteralPath $sourcePath
        $scratchPath = Get-ScratchInputPath -SourceFile $source -SafeName 'unsupported.mkv'
        Set-TestContent -Path $scratchPath -Content 'STALE--04' -LastWriteTimeUtc $source.LastWriteTimeUtc
        Write-ClaimedV2Fingerprint -ScratchPath $scratchPath -SourceFile $source -HashAlgorithm 'md5'
        $proof = Invoke-ProtectedPipelineAction -SourcePaths @($sourcePath) -Action {
            return Ensure-ScratchCopy -SourceFile $source -SafeName 'unsupported.mkv'
        }
        Assert-Equal $script:CopyCount 1 'Unsupported hash evidence must not fall back to legacy metadata matching.'
        Assert-TrustedFingerprint -ScratchPath $scratchPath -SourcePath $sourcePath | Out-Null
        return [pscustomobject]@{ Proof = $proof; Observed = 'recopied'; ScratchHashAfter = Get-TestSha256 $scratchPath; ReasonCode = 'hash_algorithm_unsupported' }
    }

    Invoke-MatrixCase -Name 'legacy_metadata_only_evidence' -ExpectedDisposition 'safe_recopy_and_migrate' -Body {
        param($env)
        $sourcePath = Join-Path $env.SourceRoot 'legacy.mkv'
        Set-TestContent -Path $sourcePath -Content 'SOURCE-05'
        $source = Get-Item -LiteralPath $sourcePath
        $scratchPath = Get-ScratchInputPath -SourceFile $source -SafeName 'legacy.mkv'
        Set-TestContent -Path $scratchPath -Content 'STALE--05' -LastWriteTimeUtc $source.LastWriteTimeUtc
        Write-LegacyFingerprint -ScratchPath $scratchPath -SourceFile $source
        $proof = Invoke-ProtectedPipelineAction -SourcePaths @($sourcePath) -Action {
            return Ensure-ScratchCopy -SourceFile $source -SafeName 'legacy.mkv'
        }
        Assert-Equal $script:CopyCount 1 'Legacy metadata-only evidence must be invalidated, never silently upgraded in place.'
        Assert-TrustedFingerprint -ScratchPath $scratchPath -SourcePath $sourcePath | Out-Null
        return [pscustomobject]@{ Proof = $proof; Observed = 'recopied_and_migrated'; ScratchHashAfter = Get-TestSha256 $scratchPath; ReasonCode = 'legacy_evidence_invalidated' }
    }

    Invoke-MatrixCase -Name 'path_alias_and_case_difference' -ExpectedDisposition 'reuse_same_canonical_source' -Body {
        param($env)
        $sourcePath = Join-Path $env.SourceRoot 'AliasMovie.mkv'
        Set-TestContent -Path $sourcePath -Content 'SOURCE-06'
        $source = Get-Item -LiteralPath $sourcePath
        $scratchPath = Ensure-ScratchCopy -SourceFile $source -SafeName 'AliasMovie.mkv'
        Assert-TrustedFingerprint -ScratchPath $scratchPath -SourcePath $sourcePath | Out-Null
        $aliasPath = Join-Path (Join-Path $env.SourceRoot '.') 'ALIASMOVIE.MKV'
        $aliasSource = [pscustomobject]@{
            FullName = $aliasPath
            Name = 'ALIASMOVIE.MKV'
            Length = [long]$source.Length
            LastWriteTimeUtc = $source.LastWriteTimeUtc
        }
        $script:CopyCount = 0
        $proof = Invoke-ProtectedPipelineAction -SourcePaths @($sourcePath) -Action {
            return Ensure-ScratchCopy -SourceFile $aliasSource -SafeName 'AliasMovie.mkv'
        }
        Assert-Equal $script:CopyCount 0 'Equivalent Windows path aliases/case must reuse content-bound scratch.'
        Assert-Equal $proof.Result $scratchPath 'Canonical alias reused a different scratch path.'
        return [pscustomobject]@{ Proof = $proof; Observed = 'reused'; ScratchHashAfter = Get-TestSha256 $scratchPath; ReasonCode = 'canonical_path_match' }
    }

    Invoke-MatrixCase -Name 'two_sources_colliding_scratch_name' -ExpectedDisposition 'safe_recopy_second_source' -Body {
        param($env)
        $sourceOneRoot = Join-Path $env.SourceRoot 'one'
        $sourceTwoRoot = Join-Path $env.SourceRoot 'two'
        $sourceOnePath = Join-Path $sourceOneRoot 'movie.mkv'
        $sourceTwoPath = Join-Path $sourceTwoRoot 'movie.mkv'
        Set-TestContent -Path $sourceOnePath -Content 'SOURCE-A1'
        Set-TestContent -Path $sourceTwoPath -Content 'SOURCE-B1'
        $sourceOne = Get-Item -LiteralPath $sourceOnePath
        $sourceTwo = Get-Item -LiteralPath $sourceTwoPath
        $scratchPathOne = Ensure-ScratchCopy -SourceFile $sourceOne -SafeName 'movie.mkv'
        $scratchPathTwo = Get-ScratchInputPath -SourceFile $sourceTwo -SafeName 'movie.mkv'
        Assert-Equal $scratchPathTwo $scratchPathOne 'Collision fixture did not map both sources to the same scratch path.'
        $script:CopyCount = 0
        $proof = Invoke-ProtectedPipelineAction -SourcePaths @($sourceOnePath, $sourceTwoPath) -Action {
            return Ensure-ScratchCopy -SourceFile $sourceTwo -SafeName 'movie.mkv'
        }
        Assert-Equal $script:CopyCount 1 'Second colliding source must replace the first source scratch safely.'
        Assert-Equal (Get-TestSha256 $scratchPathTwo) (Get-TestSha256 $sourceTwoPath) 'Colliding scratch retained first-source bytes.'
        Assert-TrustedFingerprint -ScratchPath $scratchPathTwo -SourcePath $sourceTwoPath | Out-Null
        return [pscustomobject]@{ Proof = $proof; Observed = 'recopied_second_source'; ScratchHashAfter = Get-TestSha256 $scratchPathTwo; ReasonCode = 'source_path_and_content_changed' }
    }

    Invoke-MatrixCase -Name 'prior_partial_work' -ExpectedDisposition 'safe_recopy_and_replace_partial' -Body {
        param($env)
        $sourcePath = Join-Path $env.SourceRoot 'partial.mkv'
        Set-TestContent -Path $sourcePath -Content 'SOURCE-07'
        $source = Get-Item -LiteralPath $sourcePath
        $scratchPath = Get-ScratchInputPath -SourceFile $source -SafeName 'partial.mkv'
        Set-TestContent -Path $scratchPath -Content 'PARTIAL'
        [System.IO.File]::WriteAllText("$(Get-FingerprintPath $scratchPath).orphan.tmp", '{"partial":true}')
        $proof = Invoke-ProtectedPipelineAction -SourcePaths @($sourcePath) -Action {
            return Ensure-ScratchCopy -SourceFile $source -SafeName 'partial.mkv'
        }
        Assert-Equal $script:CopyCount 1 'Prior partial scratch without trusted evidence must be replaced.'
        Assert-Equal (Get-TestSha256 $scratchPath) (Get-TestSha256 $sourcePath) 'Prior partial bytes survived scratch preparation.'
        Assert-TrustedFingerprint -ScratchPath $scratchPath -SourcePath $sourcePath | Out-Null
        return [pscustomobject]@{ Proof = $proof; Observed = 'recopied'; ScratchHashAfter = Get-TestSha256 $scratchPath; ReasonCode = 'partial_work_invalidated' }
    }

    Invoke-MatrixCase -Name 'restart_after_identity_written_before_processing' -ExpectedDisposition 'reuse_after_restart' -Body {
        param($env)
        $sourcePath = Join-Path $env.SourceRoot 'restart.mkv'
        Set-TestContent -Path $sourcePath -Content 'SOURCE-08'
        $source = Get-Item -LiteralPath $sourcePath
        $scratchPath = Ensure-ScratchCopy -SourceFile $source -SafeName 'restart.mkv'
        Assert-TrustedFingerprint -ScratchPath $scratchPath -SourcePath $sourcePath | Out-Null
        # Re-load the production module to model a new PowerShell process after
        # evidence landed but before any media-processing function was invoked.
        . $scratchCopyPath
        $script:CopyCount = 0
        $proof = Invoke-ProtectedPipelineAction -SourcePaths @($sourcePath) -Action {
            return Ensure-ScratchCopy -SourceFile (Get-Item -LiteralPath $sourcePath) -SafeName 'restart.mkv'
        }
        Assert-Equal $script:CopyCount 0 'Restart with unchanged trusted identity evidence should reuse scratch.'
        Assert-Equal $proof.Result $scratchPath 'Restart did not return the verified pre-existing scratch path.'
        return [pscustomobject]@{ Proof = $proof; Observed = 'reused_after_restart'; ScratchHashAfter = Get-TestSha256 $scratchPath; ReasonCode = 'SCRATCH_COPY_REUSED' }
    }

    Invoke-MatrixCase -Name 'locked_stale_scratch' -ExpectedDisposition 'fail_closed_no_stale_processing' -Body {
        param($env)
        $sourcePath = Join-Path $env.SourceRoot 'locked.mkv'
        Set-TestContent -Path $sourcePath -Content 'SOURCE-09'
        $source = Get-Item -LiteralPath $sourcePath
        $scratchPath = Get-ScratchInputPath -SourceFile $source -SafeName 'locked.mkv'
        Set-TestContent -Path $scratchPath -Content 'STALE--09' -LastWriteTimeUtc $source.LastWriteTimeUtc
        Write-LegacyFingerprint -ScratchPath $scratchPath -SourceFile $source
        $staleScratchHash = Get-TestSha256 -Path $scratchPath
        $lock = [System.IO.File]::Open($scratchPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::None)
        try {
            $proof = Invoke-ProtectedPipelineAction -SourcePaths @($sourcePath) -Action {
                return Ensure-ScratchCopy -SourceFile $source -SafeName 'locked.mkv'
            }
            Assert-True ($null -eq $proof.Result) 'Locked stale scratch must fail closed instead of being processed.'
            Assert-Equal $script:CopyCount 0 'Locked stale scratch must not proceed to copy over an unreplaced file.'
            $lastStage = @($script:MonitorStages | Where-Object { $_.StageId -eq 'copy_to_scratch' }) | Select-Object -Last 1
            Assert-Equal ([string]$lastStage.ReasonCode) 'SCRATCH_REPLACEMENT_BLOCKED' 'Locked stale scratch lost its fail-closed reason code.'
            return [pscustomobject]@{ Proof = $proof; Observed = 'blocked'; ScratchHashAfter = $staleScratchHash; ReasonCode = [string]$lastStage.ReasonCode }
        } finally {
            $lock.Dispose()
        }
    }
} finally {
    $matrixJson = @($caseRows) | ConvertTo-Json -Depth 12 -Compress
    Write-Output "SCRATCH_IDENTITY_CASE_MATRIX_JSON=$matrixJson"
    $campaignFull = [System.IO.Path]::GetFullPath($campaignRoot)
    $tempFull = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if ($campaignFull.StartsWith($tempFull, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Path $campaignFull -Leaf).StartsWith('mediapipeline-cpa-scratch-identity-')) {
        Remove-Item -LiteralPath $campaignFull -Recurse -Force -ErrorAction SilentlyContinue
    }
}

if ($failures.Count -gt 0) {
    throw ("Scratch identity regression failures ({0}):`n - {1}" -f $failures.Count, ($failures -join "`n - "))
}

Write-Output ("Scratch identity checks passed: {0}/{0} cases; every source hash proof matched its allowed external-mutation contract." -f $caseRows.Count)
