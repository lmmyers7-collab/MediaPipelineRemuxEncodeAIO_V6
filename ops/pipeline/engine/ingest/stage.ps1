function Get-IngestFullPath {
    param([Parameter(Mandatory = $true)] [string] $Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Test-IngestPathInsideBoundary {
    param(
        [Parameter(Mandatory = $true)] [string] $Path,
        [Parameter(Mandatory = $true)] [string] $Root
    )

    $rootFull = Get-IngestFullPath -Path $Root
    if (-not $rootFull.EndsWith([string][System.IO.Path]::DirectorySeparatorChar)) {
        $rootFull = $rootFull + [string][System.IO.Path]::DirectorySeparatorChar
    }
    $pathFull = Get-IngestFullPath -Path $Path
    return $pathFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-IngestPathEquals {
    param(
        [Parameter(Mandatory = $true)] [string] $Left,
        [Parameter(Mandatory = $true)] [string] $Right
    )

    $leftFull = (Get-IngestFullPath -Path $Left).TrimEnd('\', '/')
    $rightFull = (Get-IngestFullPath -Path $Right).TrimEnd('\', '/')
    return [string]::Equals($leftFull, $rightFull, [System.StringComparison]::OrdinalIgnoreCase)
}

function ConvertTo-IngestSafeSegment {
    param(
        [Parameter(Mandatory = $true)] [string] $Value,
        [int] $MaxLength = 80
    )

    $text = $Value.Trim()
    if ([string]::IsNullOrWhiteSpace($text)) {
        $text = [guid]::NewGuid().ToString('N')
    }
    $builder = [System.Text.StringBuilder]::new()
    foreach ($ch in $text.ToCharArray()) {
        if (($ch -ge 'a' -and $ch -le 'z') -or
            ($ch -ge 'A' -and $ch -le 'Z') -or
            ($ch -ge '0' -and $ch -le '9') -or
            $ch -eq '-' -or
            $ch -eq '_' -or
            $ch -eq '.') {
            [void]$builder.Append($ch)
        } else {
            [void]$builder.Append('-')
        }
        if ($builder.Length -ge $MaxLength) { break }
    }
    $safe = $builder.ToString().Trim('.', '-')
    if ([string]::IsNullOrWhiteSpace($safe)) {
        return [guid]::NewGuid().ToString('N')
    }
    return $safe
}

function Get-IngestSha256 {
    param([Parameter(Mandatory = $true)] [string] $Path)
    return ((Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash).ToLowerInvariant()
}

function New-IngestEvidence {
    param(
        [Parameter(Mandatory = $true)] $Payload,
        [Parameter(Mandatory = $true)] [string] $SourcePath,
        [Parameter(Mandatory = $true)] [string] $ScratchRoot,
        [Parameter(Mandatory = $true)] [string] $ScratchPath,
        [Parameter(Mandatory = $true)] [string] $EvidencePath,
        [Parameter(Mandatory = $true)] [long] $SizeBytes,
        [Parameter(Mandatory = $true)] [string] $SourceHashBefore,
        [Parameter(Mandatory = $true)] [string] $SourceHashAfter,
        [Parameter(Mandatory = $true)] [string] $ScratchHash,
        [Parameter(Mandatory = $true)] [string] $SourceMtimeBefore,
        [Parameter(Mandatory = $true)] [string] $SourceMtimeAfter,
        [Parameter(Mandatory = $true)] [bool] $SourceUnchanged,
        [Parameter(Mandatory = $true)] [string[]] $BoundaryChecks,
        [Parameter(Mandatory = $true)] [string[]] $RollbackActions,
        [Parameter(Mandatory = $true)] [string[]] $RecoveryActions
    )

    return [ordered]@{
        schema_version      = 'ingest_stage_evidence.v1'
        stage               = 'ingest'
        operation           = [string](Get-ObjectValue -Object $Payload -Name 'operation' -Default 'copy_to_scratch')
        intent              = [string](Get-ObjectValue -Object $Payload -Name 'intent' -Default '')
        run_id              = [string](Get-ObjectValue -Object $Payload -Name 'run_id' -Default '')
        job_id              = [string](Get-ObjectValue -Object $Payload -Name 'job_id' -Default '')
        created_at          = (Get-UtcNow).ToString('o')
        source_path         = $SourcePath
        scratch_root        = $ScratchRoot
        scratch_path        = $ScratchPath
        evidence_path       = $EvidencePath
        size_bytes          = $SizeBytes
        sha256              = $ScratchHash
        source_sha256       = $SourceHashBefore
        source_sha256_after = $SourceHashAfter
        source_mtime_before = $SourceMtimeBefore
        source_mtime_after  = $SourceMtimeAfter
        source_unchanged    = $SourceUnchanged
        boundary_checks     = @($BoundaryChecks)
        rollback_actions    = @($RollbackActions)
        recovery_actions    = @($RecoveryActions)
    }
}

function Write-IngestEvidence {
    param(
        [Parameter(Mandatory = $true)] [string] $EvidencePath,
        [Parameter(Mandatory = $true)] $Evidence
    )

    $evidenceDir = Split-Path -Path $EvidencePath -Parent
    if ([string]::IsNullOrWhiteSpace($evidenceDir)) {
        throw 'ingest evidence path has no parent directory'
    }
    $tmp = "$EvidencePath.$([guid]::NewGuid().ToString('N')).tmp"
    try {
        $Evidence | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $tmp -Encoding UTF8 -Force
        Move-Item -LiteralPath $tmp -Destination $EvidencePath -ErrorAction Stop
    } catch {
        if (Test-Path -LiteralPath $tmp -PathType Leaf -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
        throw
    }
}

function Invoke-IngestStage {
    param([Parameter(Mandatory = $true)] $Payload)

    $sourcePath = [string](Require-ObjectValue -Object $Payload -Name 'source_path')
    $scratchRoot = [string](Require-ObjectValue -Object $Payload -Name 'scratch_root')
    $intent = [string](Require-ObjectValue -Object $Payload -Name 'intent')
    $sourceFull = Get-IngestFullPath -Path $sourcePath
    $scratchRootFull = Get-IngestFullPath -Path $scratchRoot
    $boundaryChecks = @(
        'source is read-only input',
        'scratch target is a child of scratch_root',
        'scratch target refuses overwrite',
        'evidence path is a child of scratch_root'
    )

    if (-not (Test-Path -LiteralPath $sourceFull -PathType Leaf)) {
        throw "ingest source_path does not exist or is not a file: $sourceFull"
    }
    if ((Test-IngestPathEquals -Left $sourceFull -Right $scratchRootFull) -or
        (Test-IngestPathInsideBoundary -Path $sourceFull -Root $scratchRootFull)) {
        throw 'ingest source_path must not be inside scratch_root'
    }

    $sourceFile = Get-Item -LiteralPath $sourceFull -ErrorAction Stop
    $leaf = [System.IO.Path]::GetFileName($sourceFile.FullName)
    if ([string]::IsNullOrWhiteSpace($leaf) -or $leaf -eq '.' -or $leaf -eq '..') {
        throw 'ingest source_path does not have a safe file name'
    }
    foreach ($invalid in [System.IO.Path]::GetInvalidFileNameChars()) {
        if ($leaf.IndexOf($invalid) -ge 0) {
            throw 'ingest source_path does not have a safe file name'
        }
    }

    $identitySeed = [string](Get-ObjectValue -Object $Payload -Name 'job_id' -Default '')
    if ([string]::IsNullOrWhiteSpace($identitySeed)) {
        $identitySeed = [string](Get-ObjectValue -Object $Payload -Name 'run_id' -Default '')
    }
    if ([string]::IsNullOrWhiteSpace($identitySeed)) {
        $identitySeed = [Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes($sourceFull))).Substring(0, 16).ToLowerInvariant()
    }
    $safeIdentity = ConvertTo-IngestSafeSegment -Value $identitySeed
    $targetDir = Get-IngestFullPath -Path (Join-Path $scratchRootFull "stage_ingest_$safeIdentity")
    $scratchPath = Get-IngestFullPath -Path (Join-Path $targetDir $leaf)
    $evidencePath = "$scratchPath.ingest_evidence.json"

    if (-not (Test-IngestPathInsideBoundary -Path $targetDir -Root $scratchRootFull)) {
        throw 'ingest scratch target directory failed scratch_root boundary guard'
    }
    if (-not (Test-IngestPathInsideBoundary -Path $scratchPath -Root $targetDir)) {
        throw 'ingest scratch target failed target-directory boundary guard'
    }
    if (-not (Test-IngestPathInsideBoundary -Path $evidencePath -Root $scratchRootFull)) {
        throw 'ingest evidence path failed scratch_root boundary guard'
    }

    $sourceHashBefore = Get-IngestSha256 -Path $sourceFull
    $sourceMtimeBefore = $sourceFile.LastWriteTimeUtc.ToString('o')
    $rollbackActions = @(
        "delete scratch_path: $scratchPath",
        "delete evidence_path: $evidencePath",
        "remove empty ingest directory: $targetDir"
    )
    $recoveryActions = @(
        'if downstream validation fails, delete scratch_path and evidence_path, then rerun ingest from the original source',
        'if evidence_path exists and scratch sha256 matches, downstream stages may retry from scratch_path without touching source media'
    )

    if ($intent -eq 'dry_run') {
        return [ordered]@{
            scratch_path     = $scratchPath
            size_bytes       = [long]$sourceFile.Length
            sha256           = ''
            source_sha256    = $sourceHashBefore
            source_unchanged = $true
            evidence_path    = $evidencePath
            rollback_actions = @('dry_run only; no rollback needed')
            recovery_actions = @('execute ingest with confirm_ingest=true to create the scratch copy')
            boundary_checks  = @($boundaryChecks)
        }
    }

    if ($intent -ne 'execute') {
        throw "payload field 'intent' must be one of: dry_run, execute"
    }
    $confirm = Get-ObjectValue -Object $Payload -Name 'confirm_ingest' -Default $false
    if ($confirm -ne $true) {
        throw "payload field 'confirm_ingest' must be boolean true for ingest execute intent"
    }
    if (Test-Path -LiteralPath $scratchPath -PathType Leaf -ErrorAction SilentlyContinue) {
        throw "ingest scratch target already exists; refusing to overwrite: $scratchPath"
    }
    if (Test-Path -LiteralPath $evidencePath -PathType Leaf -ErrorAction SilentlyContinue) {
        throw "ingest evidence target already exists; refusing to overwrite: $evidencePath"
    }

    $tmpCopy = "$scratchPath.$([guid]::NewGuid().ToString('N')).tmp"
    $scratchCreated = $false
    try {
        if (-not (Test-Path -LiteralPath $targetDir -PathType Container -ErrorAction SilentlyContinue)) {
            New-Item -ItemType Directory -Path $targetDir -Force -ErrorAction Stop | Out-Null
        }
        Copy-Item -LiteralPath $sourceFull -Destination $tmpCopy -ErrorAction Stop
        $scratchHash = Get-IngestSha256 -Path $tmpCopy
        if ($scratchHash -ne $sourceHashBefore) {
            throw 'ingest scratch hash did not match source hash'
        }
        Move-Item -LiteralPath $tmpCopy -Destination $scratchPath -ErrorAction Stop
        $scratchCreated = $true

        $sourceAfter = Get-Item -LiteralPath $sourceFull -ErrorAction Stop
        $sourceHashAfter = Get-IngestSha256 -Path $sourceFull
        $sourceMtimeAfter = $sourceAfter.LastWriteTimeUtc.ToString('o')
        $sourceUnchanged = (
            $sourceHashBefore -eq $sourceHashAfter -and
            [long]$sourceFile.Length -eq [long]$sourceAfter.Length -and
            $sourceMtimeBefore -eq $sourceMtimeAfter
        )
        if (-not $sourceUnchanged) {
            throw 'ingest source changed during copy; scratch copy discarded'
        }

        $evidence = New-IngestEvidence `
            -Payload $Payload `
            -SourcePath $sourceFull `
            -ScratchRoot $scratchRootFull `
            -ScratchPath $scratchPath `
            -EvidencePath $evidencePath `
            -SizeBytes ([long]$sourceAfter.Length) `
            -SourceHashBefore $sourceHashBefore `
            -SourceHashAfter $sourceHashAfter `
            -ScratchHash $scratchHash `
            -SourceMtimeBefore $sourceMtimeBefore `
            -SourceMtimeAfter $sourceMtimeAfter `
            -SourceUnchanged $sourceUnchanged `
            -BoundaryChecks $boundaryChecks `
            -RollbackActions $rollbackActions `
            -RecoveryActions $recoveryActions
        Write-IngestEvidence -EvidencePath $evidencePath -Evidence $evidence

        return [ordered]@{
            scratch_path     = $scratchPath
            size_bytes       = [long]$sourceAfter.Length
            sha256           = $scratchHash
            source_sha256    = $sourceHashBefore
            source_unchanged = $sourceUnchanged
            evidence_path    = $evidencePath
            rollback_actions = @($rollbackActions)
            recovery_actions = @($recoveryActions)
            boundary_checks  = @($boundaryChecks)
        }
    } catch {
        if (Test-Path -LiteralPath $tmpCopy -PathType Leaf -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $tmpCopy -Force -ErrorAction SilentlyContinue
        }
        if ($scratchCreated -and (Test-Path -LiteralPath $scratchPath -PathType Leaf -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $scratchPath -Force -ErrorAction SilentlyContinue
        }
        throw
    }
}
