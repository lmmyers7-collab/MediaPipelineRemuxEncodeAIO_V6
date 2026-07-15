# Extracted from ops/pipeline/entrypoints/Invoke-RerunCsv.ps1. Responsibility: command, file transfer, configuration, and journal support

function Write-RerunLog {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "{0} [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Host $line
}

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    Write-RerunLog -Message $Message -Level $Level
}

function DebugLog {
    param([string]$Message)
    Write-RerunLog -Message $Message -Level 'DEBUG'
}

function Get-RerunValue {
    param($Row, [string[]]$Names, [string]$Default = '')
    foreach ($name in $Names) {
        $prop = $Row.PSObject.Properties[$name]
        if ($prop -and -not [string]::IsNullOrWhiteSpace([string]$prop.Value)) {
            return ([string]$prop.Value).Trim()
        }
    }
    return $Default
}

function ConvertTo-RerunBool {
    param($Value, [bool]$Default = $false)
    if ($null -eq $Value) { return $Default }
    $text = ([string]$Value).Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($text)) { return $Default }
    return @('1','true','yes','y','on','enabled','run') -contains $text
}

function Resolve-RerunChoice {
    param(
        $Row,
        [string[]]$Names,
        [string]$Default,
        [string[]]$Allowed
    )
    $value = (Get-RerunValue -Row $Row -Names $Names -Default $Default).Trim().ToLowerInvariant()
    $value = $value -replace '\s+', '_'
    if ($Allowed -contains $value) { return $value }
    return $Default
}

function Normalize-RerunChoiceValue {
    param([string]$Value)
    return (([string]$Value).Trim().ToLowerInvariant() -replace '\s+', '_')
}

function Resolve-RerunPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    $expanded = [Environment]::ExpandEnvironmentVariables($Path)
    if ([System.IO.Path]::IsPathRooted($expanded)) {
        return [System.IO.Path]::GetFullPath($expanded)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $expanded))
}

function Resolve-RerunSourcePath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    $expanded = [Environment]::ExpandEnvironmentVariables($Path)
    if (-not (Test-RerunSourcePathFullyQualified $expanded)) { return '' }
    return [System.IO.Path]::GetFullPath($expanded)
}

function Test-RerunSourcePathFullyQualified {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    $expanded = [Environment]::ExpandEnvironmentVariables($Path)
    try {
        return [System.IO.Path]::IsPathFullyQualified($expanded)
    } catch {
        if (-not [System.IO.Path]::IsPathRooted($expanded)) { return $false }
        return ($expanded -notmatch '^[A-Za-z]:[^\\/]')
    }
}

function Get-RerunValidExtensionSet {
    $set = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($item in @($script:ValidExtensions)) {
        $text = ([string]$item).Trim()
        if ([string]::IsNullOrWhiteSpace($text)) { continue }
        if (-not $text.StartsWith('.')) { $text = ".$text" }
        [void]$set.Add($text.ToLowerInvariant())
    }
    return $set
}

function Test-RerunValidMediaExtension {
    param([string]$Path)
    $extension = [System.IO.Path]::GetExtension($Path)
    if ([string]::IsNullOrWhiteSpace($extension)) { return $false }
    $valid = Get-RerunValidExtensionSet
    if ($valid.Count -eq 0) { return $false }
    return $valid.Contains($extension.ToLowerInvariant())
}

function Test-RerunUncPath {
    param([string]$Path)
    return (-not [string]::IsNullOrWhiteSpace($Path) -and ($Path.StartsWith('\\') -or $Path.StartsWith('//')))
}

function Get-RerunUncShareRoot {
    param([string]$Path)
    if (-not (Test-RerunUncPath $Path)) { return $null }
    $normalized = $Path -replace '/', '\'
    if ($normalized -match '^(\\\\[^\\]+\\[^\\]+)') {
        return ($Matches[1].TrimEnd('\') + '\')
    }
    return $null
}

function Get-RerunFreeSpaceGB {
    param([string]$Path, [int]$TimeoutSeconds = 10)
    if ([string]::IsNullOrWhiteSpace($Path)) { return -1 }
    if (Test-RerunUncPath $Path) {
        $probe = Get-RerunUncShareRoot $Path
        if ([string]::IsNullOrWhiteSpace($probe)) { return -1 }
        $job = Start-Job -ScriptBlock {
            param($ProbePath, $TypeDefinition)
            try {
                if (-not ('MediaPipeline.RerunDiskSpace' -as [type])) {
                    Add-Type -TypeDefinition $TypeDefinition -Language CSharp
                }
                [uint64]$freeAvail = 0
                [uint64]$totalBytes = 0
                [uint64]$totalFree = 0
                $ok = [MediaPipeline.RerunDiskSpace]::GetDiskFreeSpaceExW(
                    $ProbePath, [ref]$freeAvail, [ref]$totalBytes, [ref]$totalFree)
                if (-not $ok) { return -1 }
                return [math]::Round($freeAvail / 1GB, 2)
            } catch {
                return -1
            }
        } -ArgumentList $probe, $script:RerunDiskSpaceTypeDefinition
        try {
            if (Wait-Job $job -Timeout $TimeoutSeconds) {
                $result = Receive-Job $job -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($null -ne $result) { return [double]$result }
            }
            Stop-Job $job -ErrorAction SilentlyContinue
            return -1
        } finally {
            Remove-Job $job -Force -ErrorAction SilentlyContinue
        }
    }
    if ($Path -match '^([A-Za-z]):[/\\]?') {
        try {
            $di = [System.IO.DriveInfo]::new($Matches[1])
            return [math]::Round($di.AvailableFreeSpace / 1GB, 2)
        } catch {
            return -1
        }
    }
    return -1
}

function Resolve-RerunRobocopyPath {
    $systemRoot = if ($env:SystemRoot) { [string]$env:SystemRoot } else { [string]$env:windir }
    if ([string]::IsNullOrWhiteSpace($systemRoot)) { return '' }
    $candidate = Join-Path $systemRoot 'System32\robocopy.exe'
    if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    return ''
}

function Assert-RerunRobocopyFlagsSafe {
    param([array]$Flags)
    foreach ($flag in @($Flags)) {
        $token = [string]$flag
        if ($token -match '(?i)^\s*/m(?:ov(?:e)?)?(?:\s|:|$)') {
            throw 'destructive robocopy flag is forbidden for rerun scratch staging'
        }
    }
}

function Assert-RerunScratchPathBoundary {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Root,
        [switch]$AllowMissingLeaf,
        [switch]$AllowRootTarget
    )
    $boundaryHelper = Get-Command -Name Test-MediaPipelinePathBoundarySafe -CommandType Function -ErrorAction SilentlyContinue
    if ($null -eq $boundaryHelper) {
        throw 'rerun scratch path boundary helper is unavailable'
    }
    $boundary = Test-MediaPipelinePathBoundarySafe `
        -Path $Path `
        -Root $Root `
        -AllowMissingLeaf:$AllowMissingLeaf `
        -AllowRootTarget:$AllowRootTarget
    if ($null -eq $boundary -or -not [bool]$boundary.Ok) {
        $reasonCode = if ($null -eq $boundary) { 'BOUNDARY_PROOF_MISSING' } else { [string]$boundary.ReasonCode }
        $reason = if ($null -eq $boundary) { 'boundary helper returned no evidence' } else { [string]$boundary.Reason }
        throw "rerun scratch path boundary rejected: $reasonCode - $reason"
    }
    return $boundary
}

function Assert-RerunScratchTrustAnchor {
    param([Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw 'rerun scratch trust root is required'
    }
    $rootResolver = Get-Command -Name Get-MediaPipelineFilesystemBoundaryRoot -CommandType Function -ErrorAction SilentlyContinue
    if ($null -eq $rootResolver) {
        throw 'rerun scratch path boundary helper is unavailable'
    }
    try {
        if (-not [System.IO.Path]::IsPathFullyQualified($Path)) {
            throw 'path is not fully qualified'
        }
    } catch {
        throw "rerun scratch trust root is invalid: $Path"
    }
    $filesystemRoot = Get-MediaPipelineFilesystemBoundaryRoot -Path $Path
    if ([string]::IsNullOrWhiteSpace($filesystemRoot)) {
        throw "rerun scratch filesystem trust root could not be derived: $Path"
    }
    $boundary = Assert-RerunScratchPathBoundary -Path $Path -Root $filesystemRoot -AllowRootTarget
    $anchorItem = Get-Item -LiteralPath ([string]$boundary.Path) -Force -ErrorAction Stop
    if (-not ($anchorItem -is [System.IO.DirectoryInfo])) {
        throw "rerun scratch trust root is not a directory: $Path"
    }
    return $boundary
}

function New-RerunScratchDirectorySafe {
    param(
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$Path,
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$ScratchTrustRoot
    )

    $trust = Assert-RerunScratchTrustAnchor -Path $ScratchTrustRoot
    $target = Assert-RerunScratchPathBoundary -Path $Path -Root ([string]$trust.Path) -AllowMissingLeaf
    $relative = Get-MediaPipelineRelativePath -Path ([string]$target.Path) -Root ([string]$trust.Path)
    if ([string]::IsNullOrWhiteSpace($relative)) {
        throw 'rerun scratch directory must be a strict descendant of its trust root'
    }

    $current = [string]$trust.Path
    foreach ($part in ($relative -split '[\\/]')) {
        if ([string]::IsNullOrWhiteSpace($part)) { continue }
        $parent = $current
        $current = Join-Path $current $part
        Assert-RerunScratchPathBoundary -Path $parent -Root ([string]$trust.Path) -AllowRootTarget | Out-Null
        $candidate = Assert-RerunScratchPathBoundary -Path $current -Root ([string]$trust.Path) -AllowMissingLeaf
        $inspection = Get-MediaPipelinePathInspection -Path ([string]$candidate.Path)
        if (-not [bool]$inspection.Exists) {
            [System.IO.Directory]::CreateDirectory([string]$candidate.Path) | Out-Null
        }
        $created = Assert-RerunScratchPathBoundary -Path ([string]$candidate.Path) -Root ([string]$trust.Path)
        $createdItem = Get-Item -LiteralPath ([string]$created.Path) -Force -ErrorAction Stop
        if (-not ($createdItem -is [System.IO.DirectoryInfo])) {
            throw "rerun scratch directory path is not a directory: $($created.Path)"
        }
    }
    return (Assert-RerunScratchPathBoundary -Path $Path -Root ([string]$trust.Path))
}

function Get-RerunScratchMutationItem {
    param(
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$Path,
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$BatchScratchRoot,
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$ScratchTrustRoot,
        [Parameter(Mandatory)] [ValidateSet('File','Directory')] [string]$ExpectedType,
        [switch]$AllowMissing
    )

    $trust = Assert-RerunScratchTrustAnchor -Path $ScratchTrustRoot
    $batch = Assert-RerunScratchPathBoundary -Path $BatchScratchRoot -Root ([string]$trust.Path)
    $boundary = Assert-RerunScratchPathBoundary -Path $Path -Root ([string]$batch.Path) -AllowMissingLeaf:$AllowMissing
    $inspection = Get-MediaPipelinePathInspection -Path ([string]$boundary.Path)
    if (-not [bool]$inspection.Exists) {
        if ($AllowMissing) { return $null }
        throw "rerun_scratch_cleanup_ambiguous: expected scratch item is missing: $Path"
    }
    $item = $inspection.Item
    if ([bool]($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        throw "rerun_scratch_cleanup_ambiguous: scratch mutation item is a reparse point: $Path"
    }
    if ($ExpectedType -eq 'File' -and -not ($item -is [System.IO.FileInfo])) {
        throw "rerun_scratch_cleanup_ambiguous: expected scratch file but found another item type: $Path"
    }
    if ($ExpectedType -eq 'Directory' -and -not ($item -is [System.IO.DirectoryInfo])) {
        throw "rerun_scratch_cleanup_ambiguous: expected scratch directory but found another item type: $Path"
    }
    return $item
}

function Remove-RerunScratchFileSafe {
    param(
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$Path,
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$BatchScratchRoot,
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$ScratchTrustRoot,
        [switch]$AllowMissing
    )

    $item = Get-RerunScratchMutationItem -Path $Path -BatchScratchRoot $BatchScratchRoot -ScratchTrustRoot $ScratchTrustRoot -ExpectedType File -AllowMissing:$AllowMissing
    if ($null -eq $item) { return $false }
    $expectedLength = [long]$item.Length
    $expectedCreation = $item.CreationTimeUtc.Ticks
    $expectedWrite = $item.LastWriteTimeUtc.Ticks
    $confirmed = Get-RerunScratchMutationItem -Path $Path -BatchScratchRoot $BatchScratchRoot -ScratchTrustRoot $ScratchTrustRoot -ExpectedType File
    if (
        [long]$confirmed.Length -ne $expectedLength -or
        $confirmed.CreationTimeUtc.Ticks -ne $expectedCreation -or
        $confirmed.LastWriteTimeUtc.Ticks -ne $expectedWrite
    ) {
        throw "rerun_scratch_cleanup_ambiguous: scratch file identity changed before cleanup: $Path"
    }
    Remove-Item -LiteralPath $Path -Force -ErrorAction Stop
    return $true
}

function Remove-RerunScratchEmptyDirectorySafe {
    param(
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$Path,
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$BatchScratchRoot,
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$ScratchTrustRoot,
        [switch]$AllowMissing
    )

    $item = Get-RerunScratchMutationItem -Path $Path -BatchScratchRoot $BatchScratchRoot -ScratchTrustRoot $ScratchTrustRoot -ExpectedType Directory -AllowMissing:$AllowMissing
    if ($null -eq $item) { return $false }
    $children = @(Get-ChildItem -LiteralPath $Path -Force -ErrorAction Stop)
    if ($children.Count -ne 0) {
        throw "rerun_scratch_cleanup_ambiguous: scratch directory contains unexpected evidence: $Path"
    }
    $expectedCreation = $item.CreationTimeUtc.Ticks
    $confirmed = Get-RerunScratchMutationItem -Path $Path -BatchScratchRoot $BatchScratchRoot -ScratchTrustRoot $ScratchTrustRoot -ExpectedType Directory
    if ($confirmed.CreationTimeUtc.Ticks -ne $expectedCreation) {
        throw "rerun_scratch_cleanup_ambiguous: scratch directory identity changed before cleanup: $Path"
    }
    Remove-Item -LiteralPath $Path -Force -ErrorAction Stop
    return $true
}

function Clear-RerunCopyAttemptArtifacts {
    param(
        [Parameter(Mandatory)] [string]$AttemptDirectory,
        [Parameter(Mandatory)] [string]$ExpectedLandedPath,
        [Parameter(Mandatory)] [string]$PartialPath,
        [Parameter(Mandatory)] [string]$BatchScratchRoot,
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$ScratchTrustRoot
    )
    try {
        Assert-RerunScratchTrustAnchor -Path $ScratchTrustRoot | Out-Null
        Assert-RerunScratchPathBoundary -Path $BatchScratchRoot -Root $ScratchTrustRoot | Out-Null
        Assert-RerunScratchPathBoundary -Path $AttemptDirectory -Root $BatchScratchRoot -AllowMissingLeaf | Out-Null
        Assert-RerunScratchPathBoundary -Path $ExpectedLandedPath -Root $BatchScratchRoot -AllowMissingLeaf | Out-Null
        Assert-RerunScratchPathBoundary -Path $PartialPath -Root $BatchScratchRoot -AllowMissingLeaf | Out-Null

        $attemptItem = Get-RerunScratchMutationItem -Path $AttemptDirectory -BatchScratchRoot $BatchScratchRoot -ScratchTrustRoot $ScratchTrustRoot -ExpectedType Directory -AllowMissing
        $landedItem = Get-RerunScratchMutationItem -Path $ExpectedLandedPath -BatchScratchRoot $BatchScratchRoot -ScratchTrustRoot $ScratchTrustRoot -ExpectedType File -AllowMissing
        $partialItem = Get-RerunScratchMutationItem -Path $PartialPath -BatchScratchRoot $BatchScratchRoot -ScratchTrustRoot $ScratchTrustRoot -ExpectedType File -AllowMissing
        if ($null -ne $attemptItem) {
            $children = @(Get-ChildItem -LiteralPath $AttemptDirectory -Force -ErrorAction Stop)
            $expectedFullPath = [System.IO.Path]::GetFullPath($ExpectedLandedPath)
            $unexpected = @($children | Where-Object {
                -not ([System.IO.Path]::GetFullPath([string]$_.FullName).Equals($expectedFullPath, [System.StringComparison]::OrdinalIgnoreCase))
            })
            if ($unexpected.Count -gt 0 -or $children.Count -gt 1) {
                throw "rerun_scratch_cleanup_ambiguous: scratch attempt contains unexpected evidence: $AttemptDirectory"
            }
        }

        if ($null -ne $partialItem) {
            Remove-RerunScratchFileSafe -Path $PartialPath -BatchScratchRoot $BatchScratchRoot -ScratchTrustRoot $ScratchTrustRoot | Out-Null
        }
        if ($null -ne $landedItem) {
            Remove-RerunScratchFileSafe -Path $ExpectedLandedPath -BatchScratchRoot $BatchScratchRoot -ScratchTrustRoot $ScratchTrustRoot | Out-Null
        }
        if ($null -ne $attemptItem) {
            Remove-RerunScratchEmptyDirectorySafe -Path $AttemptDirectory -BatchScratchRoot $BatchScratchRoot -ScratchTrustRoot $ScratchTrustRoot | Out-Null
        }
    } catch {
        $message = [string]$_.Exception.Message
        if ($message -match '^rerun_scratch_cleanup_ambiguous:') { throw }
        throw "rerun_scratch_cleanup_ambiguous: scratch attempt cleanup proof failed: $message"
    }
}

function Move-RerunStageAttemptToDestination {
    param(
        [Parameter(Mandatory)] [string]$LandedPath,
        [Parameter(Mandatory)] [string]$PartialPath,
        [Parameter(Mandatory)] [string]$Destination,
        [Parameter(Mandatory)] [string]$BatchScratchRoot,
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$ScratchTrustRoot,
        [scriptblock]$BeforeFinalMove = $null
    )
    Assert-RerunScratchTrustAnchor -Path $ScratchTrustRoot | Out-Null
    Assert-RerunScratchPathBoundary -Path $BatchScratchRoot -Root $ScratchTrustRoot | Out-Null
    Assert-RerunScratchPathBoundary -Path $LandedPath -Root $BatchScratchRoot | Out-Null
    Assert-RerunScratchPathBoundary -Path $PartialPath -Root $BatchScratchRoot -AllowMissingLeaf | Out-Null
    Assert-RerunScratchPathBoundary -Path $Destination -Root $BatchScratchRoot -AllowMissingLeaf | Out-Null
    if (Test-Path -LiteralPath $PartialPath) {
        throw "rerun_scratch_cleanup_ambiguous: promotion partial already exists: $PartialPath"
    }
    if (Test-Path -LiteralPath $Destination) {
        throw "stage path already exists: $Destination"
    }
    $partialCreated = $false
    try {
        [System.IO.File]::Move($LandedPath, $PartialPath)
        $partialCreated = $true
        if ($null -ne $BeforeFinalMove) { & $BeforeFinalMove $PartialPath $Destination }
        Assert-RerunScratchTrustAnchor -Path $ScratchTrustRoot | Out-Null
        Assert-RerunScratchPathBoundary -Path $BatchScratchRoot -Root $ScratchTrustRoot | Out-Null
        Assert-RerunScratchPathBoundary -Path $PartialPath -Root $BatchScratchRoot | Out-Null
        Assert-RerunScratchPathBoundary -Path $Destination -Root $BatchScratchRoot -AllowMissingLeaf | Out-Null
        if (Test-Path -LiteralPath $Destination) { throw "stage path appeared during copy: $Destination" }
        [System.IO.File]::Move($PartialPath, $Destination)
        $partialCreated = $false
    } catch {
        $originalMessage = [string]$_.Exception.Message
        if ($partialCreated) {
            try {
                Remove-RerunScratchFileSafe -Path $PartialPath -BatchScratchRoot $BatchScratchRoot -ScratchTrustRoot $ScratchTrustRoot | Out-Null
            } catch {
                throw "rerun_scratch_cleanup_ambiguous: post-move cleanup was refused; original=$originalMessage; cleanup=$($_.Exception.Message)"
            }
        }
        throw $originalMessage
    }
}

function Copy-RerunFileVerified {
    param(
        [Parameter(Mandatory)] [string]$Source,
        [Parameter(Mandatory)] [string]$Destination,
        [int]$MaxRetries = 3,
        [Nullable[long]]$ExpectedSize = $null,
        [string]$ExpectedMtimeUtc = '',
        [string]$ExpectedIdentityV2 = '',
        [string]$ExpectedContentSha256 = '',
        [string]$SourceRootPath = '',
        [string]$FfprobePath = '',
        [ValidateRange(1, 7200)] [int]$ContentHashTimeoutSeconds = 1800,
        [string]$BatchScratchRoot = '',
        [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string]$ScratchTrustRoot,
        [string]$AttemptId = ''
    )
    if (-not [string]::IsNullOrWhiteSpace($AttemptId) -and $AttemptId -cnotmatch '^[A-Za-z0-9_-]+$') {
        throw 'rerun stage attempt id must contain only letters, numbers, underscores, and hyphens'
    }
    $flags = if ($script:RerunRobocopyFlags) { @($script:RerunRobocopyFlags) } else { @('/J', '/R:3', '/W:15', '/MT:2', '/NP', '/NDL', '/NFL') }
    Assert-RerunRobocopyFlagsSafe -Flags $flags
    $robocopy = Resolve-RerunRobocopyPath
    if ([string]::IsNullOrWhiteSpace($robocopy)) {
        throw 'robocopy.exe was not found at the expected System32 path'
    }
    $effectiveExpectedIdentity = $ExpectedIdentityV2
    $effectiveExpectedContentSha256 = $ExpectedContentSha256
    if (Get-Command Get-RerunSourceHealth -ErrorAction SilentlyContinue) {
        $initialHealth = Get-RerunSourceHealth `
            -SourcePath $Source `
            -ExpectedIdentityV2 $ExpectedIdentityV2 `
            -ExpectedContentSha256 $ExpectedContentSha256 `
            -ExpectedSize $ExpectedSize `
            -ExpectedMtimeUtc $ExpectedMtimeUtc `
            -ConfiguredRootPath $SourceRootPath `
            -IdentityTimeoutSeconds $ContentHashTimeoutSeconds `
            -FfprobePath $FfprobePath
        if (-not $initialHealth.Available) { throw "$($initialHealth.Code): $($initialHealth.Message)" }
        $srcItem = $initialHealth.FileInfo
        $effectiveExpectedIdentity = [string]$initialHealth.IdentityV2
        $effectiveExpectedContentSha256 = [string]$initialHealth.ContentSha256
    } else {
        $srcItem = Get-Item -LiteralPath $Source -ErrorAction Stop
        if (-not ($srcItem -is [System.IO.FileInfo])) { throw "source path is not a file: $Source" }
        if ([string]::IsNullOrWhiteSpace($effectiveExpectedIdentity) -and (Get-Command Get-RerunSourceIdentityV2 -ErrorAction SilentlyContinue)) {
            $effectiveExpectedIdentity = Get-RerunSourceIdentityV2 -FileInfo $srcItem -FfprobePath $FfprobePath
        }
    }
    $effectiveExpectedSize = if ($null -ne $ExpectedSize) { [long]$ExpectedSize } else { [long]$srcItem.Length }
    $effectiveExpectedMtimeUtc = if ([string]::IsNullOrWhiteSpace($ExpectedMtimeUtc)) { $srcItem.LastWriteTimeUtc.ToString('o') } else { $ExpectedMtimeUtc }

    $srcDir = Split-Path -Parent $Source
    $srcLeaf = Split-Path -Leaf $Source
    $dstDir = Split-Path -Parent $Destination
    $dstLeaf = Split-Path -Leaf $Destination
    if ([string]::IsNullOrWhiteSpace($BatchScratchRoot)) { $BatchScratchRoot = $dstDir }
    $stagingRoot = Join-Path $BatchScratchRoot '.mediapipeline-rerun-staging'
    Assert-RerunScratchTrustAnchor -Path $ScratchTrustRoot | Out-Null
    Assert-RerunScratchPathBoundary -Path $BatchScratchRoot -Root $ScratchTrustRoot -AllowMissingLeaf | Out-Null
    if (-not (Test-Path -LiteralPath $BatchScratchRoot -PathType Container)) {
        New-RerunScratchDirectorySafe -Path $BatchScratchRoot -ScratchTrustRoot $ScratchTrustRoot | Out-Null
    }
    Assert-RerunScratchPathBoundary -Path $BatchScratchRoot -Root $ScratchTrustRoot | Out-Null
    Assert-RerunScratchPathBoundary -Path $Destination -Root $BatchScratchRoot -AllowMissingLeaf | Out-Null
    Assert-RerunScratchPathBoundary -Path $stagingRoot -Root $BatchScratchRoot -AllowMissingLeaf | Out-Null
    if (-not (Test-Path -LiteralPath $dstDir)) {
        New-RerunScratchDirectorySafe -Path $dstDir -ScratchTrustRoot $BatchScratchRoot | Out-Null
    }
    Assert-RerunScratchPathBoundary -Path $dstDir -Root $BatchScratchRoot -AllowRootTarget | Out-Null
    Assert-RerunScratchPathBoundary -Path $Destination -Root $BatchScratchRoot -AllowMissingLeaf | Out-Null
    if (Test-Path -LiteralPath $Destination) { throw "stage path already exists: $Destination" }

    $freeGB = Get-RerunFreeSpaceGB -Path $dstDir
    $requiredGB = ([double]$srcItem.Length / 1GB) + 0.5
    if ($freeGB -lt 0) {
        throw "unable to determine free space for rerun stage destination: $dstDir"
    }
    if ($freeGB -lt $requiredGB) {
        throw ("insufficient free space at rerun stage destination: {0:N2} GB free, need {1:N2} GB" -f $freeGB, $requiredGB)
    }

    if (-not (Test-Path -LiteralPath $stagingRoot)) {
        New-RerunScratchDirectorySafe -Path $stagingRoot -ScratchTrustRoot $BatchScratchRoot | Out-Null
    }
    Assert-RerunScratchPathBoundary -Path $stagingRoot -Root $BatchScratchRoot | Out-Null
    $timeoutSeconds = if ($script:RerunRobocopyTimeoutSeconds -gt 0) { [int]$script:RerunRobocopyTimeoutSeconds } else { 14400 }

    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        $copyId = if (-not [string]::IsNullOrWhiteSpace($AttemptId) -and $MaxRetries -eq 1) { $AttemptId } else { [guid]::NewGuid().ToString('N') }
        $attemptDir = Join-Path $stagingRoot $copyId
        $landed = Join-Path $attemptDir $srcLeaf
        $partial = Join-Path $dstDir "$dstLeaf.rerun-partial.$copyId"
        Assert-RerunScratchPathBoundary -Path $attemptDir -Root $BatchScratchRoot -AllowMissingLeaf | Out-Null
        Assert-RerunScratchPathBoundary -Path $landed -Root $BatchScratchRoot -AllowMissingLeaf | Out-Null
        Assert-RerunScratchPathBoundary -Path $partial -Root $BatchScratchRoot -AllowMissingLeaf | Out-Null
        if (Test-Path -LiteralPath $partial) {
            throw "rerun_scratch_cleanup_ambiguous: attempt partial already exists: $partial"
        }
        $attemptArtifactsCleared = $false
        try {
            New-RerunScratchDirectorySafe -Path $attemptDir -ScratchTrustRoot $BatchScratchRoot | Out-Null
            Assert-RerunScratchPathBoundary -Path $BatchScratchRoot -Root $ScratchTrustRoot | Out-Null
            Assert-RerunScratchPathBoundary -Path $attemptDir -Root $BatchScratchRoot | Out-Null
            Assert-RerunScratchPathBoundary -Path $landed -Root $BatchScratchRoot -AllowMissingLeaf | Out-Null
            Write-RerunLog "STAGE COPY attempt $attempt/${MaxRetries}: $srcLeaf -> $Destination" "INFO"
            $result = Invoke-RerunNativeCommand -FilePath $robocopy -ArgumentList (@($srcDir, $attemptDir, $srcLeaf) + $flags + @('/DCOPY:DA')) -TimeoutSeconds $timeoutSeconds -Label 'robocopy-rerun-stage'
            if ($result.TimedOut) {
                Write-RerunLog "Rerun stage robocopy timed out after ${timeoutSeconds}s for $Source" "ERROR"
            }
            if ([int]$result.ExitCode -in @(0, 1, 3)) {
                $landedItem = Get-Item -LiteralPath $landed -ErrorAction Stop
                if ([long]$landedItem.Length -ne [long]$effectiveExpectedSize) {
                    throw "source_identity_changed: staged copy size mismatch: expected=$effectiveExpectedSize staged=$($landedItem.Length)"
                }
                if (Get-Command Get-RerunSourceHealth -ErrorAction SilentlyContinue) {
                    # The source was validated immediately before copy. Verify the landed bytes
                    # against that durable identity so a post-copy outage cannot discard good scratch.
                    $landedHealth = Get-RerunSourceHealth `
                        -SourcePath $landed `
                        -ExpectedIdentityV2 $effectiveExpectedIdentity `
                        -ExpectedContentSha256 $effectiveExpectedContentSha256 `
                        -ExpectedSize $effectiveExpectedSize `
                        -ConfiguredRootPath $BatchScratchRoot `
                        -IdentityTimeoutSeconds $ContentHashTimeoutSeconds `
                        -FfprobePath $FfprobePath
                    if (-not $landedHealth.Available) { throw "$($landedHealth.Code): staged scratch verification failed: $($landedHealth.Message)" }
                }
                Move-RerunStageAttemptToDestination -LandedPath $landed -PartialPath $partial -Destination $Destination -BatchScratchRoot $BatchScratchRoot -ScratchTrustRoot $ScratchTrustRoot
                Assert-RerunScratchTrustAnchor -Path $ScratchTrustRoot | Out-Null
                Assert-RerunScratchPathBoundary -Path $BatchScratchRoot -Root $ScratchTrustRoot | Out-Null
                Assert-RerunScratchPathBoundary -Path $Destination -Root $BatchScratchRoot | Out-Null
                $finalStageItem = Get-Item -LiteralPath $Destination -Force -ErrorAction Stop
                if ([long]$finalStageItem.Length -ne [long]$effectiveExpectedSize) {
                    throw 'rerun_scratch_cleanup_ambiguous: promoted staged scratch size changed after verified promotion; evidence was preserved'
                }
                return $true
            }
            Write-RerunLog "Rerun stage robocopy failed with exit $($result.ExitCode): $($result.Error)" "WARN"
            throw "stage_copy_failed: robocopy exit $($result.ExitCode): $($result.Error)"
        } catch {
            $copyFailureMessage = [string]$_.Exception.Message
            Write-RerunLog "Rerun stage copy attempt $attempt failed: $copyFailureMessage" "WARN"
            $attemptArtifactsCleared = $true
            Clear-RerunCopyAttemptArtifacts -AttemptDirectory $attemptDir -ExpectedLandedPath $landed -PartialPath $partial -BatchScratchRoot $BatchScratchRoot -ScratchTrustRoot $ScratchTrustRoot
            if (
                $copyFailureMessage -match '^(source_location_unavailable|source_missing|source_access_failed|source_identity_changed):' -or
                $copyFailureMessage -match '^rerun_scratch_cleanup_ambiguous:' -or
                $copyFailureMessage -match '^rerun scratch path boundary rejected:' -or
                $copyFailureMessage -match '^rerun scratch path boundary helper is unavailable'
            ) {
                throw
            }
            if (Get-Command Get-RerunSourceHealth -ErrorAction SilentlyContinue) {
                $failureHealth = Get-RerunSourceHealth `
                    -SourcePath $Source `
                    -ExpectedIdentityV2 $effectiveExpectedIdentity `
                    -ExpectedContentSha256 $effectiveExpectedContentSha256 `
                    -ExpectedSize $effectiveExpectedSize `
                    -ExpectedMtimeUtc $effectiveExpectedMtimeUtc `
                    -ConfiguredRootPath $SourceRootPath `
                    -IdentityTimeoutSeconds $ContentHashTimeoutSeconds `
                    -FfprobePath $FfprobePath
                if (-not $failureHealth.Available) {
                    throw "$($failureHealth.Code): $($failureHealth.Message)"
                }
            }
        } finally {
            if (-not $attemptArtifactsCleared) {
                $attemptArtifactsCleared = $true
                Clear-RerunCopyAttemptArtifacts -AttemptDirectory $attemptDir -ExpectedLandedPath $landed -PartialPath $partial -BatchScratchRoot $BatchScratchRoot -ScratchTrustRoot $ScratchTrustRoot
            }
            Assert-RerunScratchPathBoundary -Path $BatchScratchRoot -Root $ScratchTrustRoot | Out-Null
            Assert-RerunScratchPathBoundary -Path $stagingRoot -Root $BatchScratchRoot -AllowMissingLeaf | Out-Null
            if (Test-Path -LiteralPath $stagingRoot) {
                $children = @(Get-ChildItem -LiteralPath $stagingRoot -Force -ErrorAction Stop)
                if ($children.Count -eq 0) {
                    Remove-RerunScratchEmptyDirectorySafe -Path $stagingRoot -BatchScratchRoot $BatchScratchRoot -ScratchTrustRoot $ScratchTrustRoot | Out-Null
                }
            }
        }
        if ($attempt -lt $MaxRetries) { Start-Sleep -Seconds 5 }
    }
    return $false
}

function Add-RerunCommandTail {
    param(
        [Parameter(Mandatory)] [System.Text.StringBuilder]$Builder,
        [AllowNull()] [string]$Text,
        [int]$MaxChars = 65536
    )
    if ($null -eq $Text) { return }
    [void]$Builder.AppendLine($Text)
    if ($Builder.Length -gt $MaxChars) {
        $remove = $Builder.Length - $MaxChars
        try { [void]$Builder.Remove(0, $remove) } catch {}
    }
}

function Invoke-RerunStreamingCommand {
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [array]$ArgumentList = @(),
        [int]$TimeoutSeconds = 0,
        [string]$Label = 'command'
    )
    $psi = [System.Diagnostics.ProcessStartInfo]@{
        FileName               = $FilePath
        UseShellExecute        = $false
        RedirectStandardError  = $true
        RedirectStandardOutput = $true
        CreateNoWindow         = $true
    }
    foreach ($arg in @($ArgumentList)) { [void]$psi.ArgumentList.Add([string]$arg) }

    $proc = $null
    $stdoutTask = $null
    $stderrTask = $null
    $stdoutTail = [System.Text.StringBuilder]::new()
    $stderrTail = [System.Text.StringBuilder]::new()
    $startedAt = Get-Date
    $timedOut = $false
    try {
        $proc = [System.Diagnostics.Process]::Start($psi)
        $stdoutTask = $proc.StandardOutput.ReadLineAsync()
        $stderrTask = $proc.StandardError.ReadLineAsync()
        while (-not $proc.HasExited) {
            if ($TimeoutSeconds -gt 0 -and ((Get-Date) - $startedAt).TotalSeconds -ge $TimeoutSeconds) {
                $timedOut = $true
                Write-RerunLog "$Label timed out after ${TimeoutSeconds}s; killing process tree" "ERROR"
                Stop-RerunNativeProcessTree -Process $proc -Label $Label
                break
            }
            if ($stdoutTask -and $stdoutTask.IsCompleted) {
                $line = $stdoutTask.Result
                if ($null -ne $line) {
                    Add-RerunCommandTail -Builder $stdoutTail -Text $line
                    if ($line.Trim()) { Write-RerunLog $line "INFO" }
                    $stdoutTask = $proc.StandardOutput.ReadLineAsync()
                }
            }
            if ($stderrTask -and $stderrTask.IsCompleted) {
                $line = $stderrTask.Result
                if ($null -ne $line) {
                    Add-RerunCommandTail -Builder $stderrTail -Text $line
                    if ($line.Trim()) { Write-RerunLog $line "WARN" }
                    $stderrTask = $proc.StandardError.ReadLineAsync()
                }
            }
            Start-Sleep -Milliseconds 100
        }
        if ($timedOut) {
            try { $proc.WaitForExit(5000) | Out-Null } catch {}
        } else {
            try { $proc.WaitForExit() } catch {}
        }
        $drainUntil = (Get-Date).AddSeconds(2)
        foreach ($stream in @('stdout','stderr')) {
            $task = if ($stream -eq 'stdout') { $stdoutTask } else { $stderrTask }
            while ($task -and (Get-Date) -lt $drainUntil) {
                if (-not ($task.IsCompleted -or $task.Wait(100))) { continue }
                $line = $task.Result
                if ($null -eq $line) { break }
                if ($stream -eq 'stdout') {
                    Add-RerunCommandTail -Builder $stdoutTail -Text $line
                    if ($line.Trim()) { Write-RerunLog $line "INFO" }
                    $task = $proc.StandardOutput.ReadLineAsync()
                    $stdoutTask = $task
                } else {
                    Add-RerunCommandTail -Builder $stderrTail -Text $line
                    if ($line.Trim()) { Write-RerunLog $line "WARN" }
                    $task = $proc.StandardError.ReadLineAsync()
                    $stderrTask = $task
                }
            }
        }
    } catch {
        return [pscustomobject]@{
            ExitCode = -2
            TimedOut = $false
            OutputTail = $stdoutTail.ToString()
            ErrorTail = "Failed to run ${Label}: $_"
        }
    }
    if ($timedOut) {
        Add-RerunCommandTail -Builder $stderrTail -Text "[KILLED: TIMEOUT after ${TimeoutSeconds}s]"
    }
    return [pscustomobject]@{
        ExitCode = if ($timedOut) { -1 } else { [int]$proc.ExitCode }
        TimedOut = $timedOut
        OutputTail = $stdoutTail.ToString()
        ErrorTail = $stderrTail.ToString()
    }
}

function ConvertTo-Psd1KeyLiteral {
    param([object]$Key)
    $text = [string]$Key
    $escaped = $text -replace "'", "''"
    return "'$escaped'"
}

function ConvertTo-Psd1Literal {
    param($Value, [int]$Indent = 0)
    $pad = ' ' * $Indent
    if ($null -eq $Value) { return '$null' }
    if ($Value -is [bool]) { return $(if ($Value) { '$true' } else { '$false' }) }
    if ($Value -is [int] -or $Value -is [long] -or $Value -is [double] -or $Value -is [decimal]) {
        return ([string]$Value)
    }
    if ($Value -is [System.Collections.IDictionary]) {
        $lines = [System.Collections.Generic.List[string]]::new()
        $lines.Add('@{')
        foreach ($key in $Value.Keys) {
            $safeKey = ConvertTo-Psd1KeyLiteral -Key $key
            $lines.Add(('{0}    {1} = {2}' -f $pad, $safeKey, (ConvertTo-Psd1Literal -Value $Value[$key] -Indent ($Indent + 4))))
        }
        $lines.Add("$pad}")
        return ($lines -join [Environment]::NewLine)
    }
    if ($Value -is [array]) {
        $items = @($Value | ForEach-Object { ConvertTo-Psd1Literal -Value $_ -Indent $Indent })
        return '@(' + ($items -join ', ') + ')'
    }
    $escaped = ([string]$Value) -replace "'", "''"
    return "'$escaped'"
}

function Copy-RerunConfigValue {
    param($Value)
    if ($null -eq $Value) { return $null }
    if ($Value -is [System.Collections.IDictionary]) {
        $copy = [ordered]@{}
        foreach ($key in $Value.Keys) {
            $copy[[string]$key] = Copy-RerunConfigValue -Value $Value[$key]
        }
        return $copy
    }
    if ($Value -is [array]) {
        return @($Value | ForEach-Object { Copy-RerunConfigValue -Value $_ })
    }
    return $Value
}

function Get-RerunProfileField {
    param($Profile, [string]$Name, [string]$Default = '')
    if ($Profile -is [System.Collections.IDictionary] -and $Profile.Contains($Name)) {
        return [string]$Profile[$Name]
    }
    $prop = $Profile.PSObject.Properties[$Name]
    if ($prop) { return [string]$prop.Value }
    return $Default
}

function Set-RerunProfileField {
    param($Profile, [string]$Name, $Value)
    if ($Profile -is [System.Collections.IDictionary]) {
        $Profile[$Name] = $Value
    }
}

function New-RerunLibraryProfiles {
    param(
        $Profiles,
        [string]$StageRoot,
        [string]$OutputRoot
    )

    $stageMoviesRoot = Join-Path $StageRoot 'Movies'
    $stageTvRoot = Join-Path $StageRoot 'TV'
    $rewritten = [System.Collections.Generic.List[object]]::new()
    foreach ($profile in @($Profiles)) {
        $copy = Copy-RerunConfigValue -Value $profile
        $id = (Get-RerunProfileField -Profile $copy -Name 'id').Trim().ToLowerInvariant()
        $designation = (Get-RerunProfileField -Profile $copy -Name 'designation').Trim().ToLowerInvariant()
        if ($designation -in @('mixed','custom','')) { $designation = 'auto' }

        if ($designation -eq 'movie' -or $id -eq 'movies') {
            Set-RerunProfileField -Profile $copy -Name 'source_path' -Value $stageMoviesRoot
            Set-RerunProfileField -Profile $copy -Name 'output_path' -Value $OutputRoot
            Set-RerunProfileField -Profile $copy -Name 'enabled' -Value $true
        } elseif ($designation -eq 'tv' -or $id -eq 'tv') {
            Set-RerunProfileField -Profile $copy -Name 'source_path' -Value $stageTvRoot
            Set-RerunProfileField -Profile $copy -Name 'output_path' -Value $OutputRoot
            Set-RerunProfileField -Profile $copy -Name 'enabled' -Value $true
        } else {
            Set-RerunProfileField -Profile $copy -Name 'enabled' -Value $false
        }
        Set-RerunProfileField -Profile $copy -Name 'promotion_enabled' -Value $false
        Set-RerunProfileField -Profile $copy -Name 'promotion_destination' -Value ''
        [void]$rewritten.Add($copy)
    }
    return @($rewritten)
}

function Move-RerunFileReplaceWithRetry {
    param(
        [Parameter(Mandatory)] [string]$Source,
        [Parameter(Mandatory)] [string]$Destination,
        [string]$Label = 'file replace',
        [int]$Attempts = 20,
        [int]$DelayMilliseconds = 250
    )
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            [System.IO.File]::Move($Source, $Destination, $true)
            return
        } catch {
            if ($attempt -ge $Attempts) { throw }
            $message = if ($_.Exception -and $_.Exception.Message) { [string]$_.Exception.Message } else { [string]$_ }
            Write-RerunLog "$Label replace attempt $attempt/$Attempts failed; retrying: $message" "WARN"
            Start-Sleep -Milliseconds $DelayMilliseconds
        }
    }
}

function Write-RerunTempConfig {
    param(
        [hashtable]$Config,
        [string]$Path
    )
    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add('@{')
    foreach ($key in ($Config.Keys | Sort-Object)) {
        $safeKey = ConvertTo-Psd1KeyLiteral -Key $key
        $lines.Add(('    {0} = {1}' -f $safeKey, (ConvertTo-Psd1Literal -Value $Config[$key] -Indent 4)))
    }
    $lines.Add('}')

    $dir = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $tmp = Join-Path $dir ('.' + (Split-Path -Leaf $Path) + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
    [System.IO.File]::WriteAllText($tmp, ($lines -join [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
    Move-RerunFileReplaceWithRetry -Source $tmp -Destination $Path -Label 'CSV rerun temp config'
}

function Get-RerunManifestMutexName {
    param([Parameter(Mandatory)] [string]$Path)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes([System.IO.Path]::GetFullPath($Path).ToLowerInvariant())
        $hash = [System.BitConverter]::ToString($sha.ComputeHash($bytes)).Replace('-', '').Substring(0, 24)
        return "Global\MediaPipelineRerunManifest_$hash"
    } finally {
        if ($sha) { $sha.Dispose() }
    }
}

function Write-RerunManifest {
    param(
        [string]$Path,
        $Payload
    )
    $mutex = $null
    $acquired = $false
    $tmp = ''
    $payloadSequenceMutated = $false
    $payloadSequenceCommitted = $false
    $payloadHadWriteSequence = $false
    $payloadOriginalWriteSequence = $null
    try {
        $mutex = [System.Threading.Mutex]::new($false, (Get-RerunManifestMutexName -Path $Path))
        try {
            $acquired = $mutex.WaitOne(30000)
        } catch [System.Threading.AbandonedMutexException] {
            $acquired = $true
        }
        if (-not $acquired) { throw "Timed out waiting for CSV rerun manifest writer lock: $Path" }

    $payloadSequence = 0
    $payloadBatchId = ''
    $payloadLifecycleState = ''
    $payloadSchemaVersion = ''
    if ($Payload -is [System.Collections.IDictionary]) {
        if ($Payload.Contains('write_sequence')) { try { $payloadSequence = [int]$Payload['write_sequence'] } catch {} }
        if ($Payload.Contains('batch_id')) { $payloadBatchId = [string]$Payload['batch_id'] }
        if ($Payload.Contains('lifecycle_state')) { $payloadLifecycleState = [string]$Payload['lifecycle_state'] }
        if ($Payload.Contains('schema_version')) { $payloadSchemaVersion = [string]$Payload['schema_version'] }
    } else {
        if ($Payload.PSObject.Properties['write_sequence']) { try { $payloadSequence = [int]$Payload.write_sequence } catch {} }
        if ($Payload.PSObject.Properties['batch_id']) { $payloadBatchId = [string]$Payload.batch_id }
        if ($Payload.PSObject.Properties['lifecycle_state']) { $payloadLifecycleState = [string]$Payload.lifecycle_state }
        if ($Payload.PSObject.Properties['schema_version']) { $payloadSchemaVersion = [string]$Payload.schema_version }
    }
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        try {
            $existing = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
            $existingBatchId = [string]$existing.batch_id
            $existingSchemaVersion = [string]$existing.schema_version
            $existingSequence = 0
            try { $existingSequence = [int]$existing.write_sequence } catch {}
            $strictExecutionManifest = ($payloadSchemaVersion -eq 'rerun_batch_manifest.v2' -and $existingSchemaVersion -eq 'rerun_batch_manifest.v2')
            if ($strictExecutionManifest) {
                if ([string]::IsNullOrWhiteSpace($payloadBatchId) -or [string]::IsNullOrWhiteSpace($existingBatchId) -or -not $payloadBatchId.Equals($existingBatchId, [System.StringComparison]::Ordinal)) {
                    throw "CSV rerun manifest write rejected: batch_id mismatch disk=$existingBatchId payload=$payloadBatchId"
                }
                if ($existingSequence -ne $payloadSequence) {
                    throw "stale CSV rerun manifest write rejected: sequence mismatch disk_sequence=$existingSequence payload_sequence=$payloadSequence"
                }
            } elseif ($existingSequence -gt $payloadSequence) {
                throw "stale CSV rerun manifest write rejected: disk_sequence=$existingSequence payload_sequence=$payloadSequence"
            }
            if ([string]$existing.lifecycle_state -eq 'terminal' -and $payloadLifecycleState -ne 'terminal') {
                throw 'stale CSV rerun manifest write rejected: terminal manifest cannot regress to a nonterminal state'
            }
        } catch {
            if ($_.Exception.Message -like 'stale CSV rerun manifest write rejected:*' -or $_.Exception.Message -like 'CSV rerun manifest write rejected:*') { throw }
            throw "CSV rerun manifest could not be safely compared before replace: $($_.Exception.Message)"
        }
    } elseif ($payloadSchemaVersion -eq 'rerun_batch_manifest.v2' -and $payloadSequence -ne 0) {
        throw "stale CSV rerun manifest write rejected: new v2 manifest must start from payload_sequence=0, got $payloadSequence"
    }
    $nextWriteSequence = $payloadSequence + 1
    if ($Payload -is [System.Collections.IDictionary]) {
        $payloadHadWriteSequence = $Payload.Contains('write_sequence')
        if ($payloadHadWriteSequence) { $payloadOriginalWriteSequence = $Payload['write_sequence'] }
        $Payload['write_sequence'] = $nextWriteSequence
    } elseif ($Payload.PSObject.Properties['write_sequence']) {
        $payloadHadWriteSequence = $true
        $payloadOriginalWriteSequence = $Payload.write_sequence
        $Payload.write_sequence = $nextWriteSequence
    } else {
        $Payload | Add-Member -NotePropertyName 'write_sequence' -NotePropertyValue $nextWriteSequence
    }
    $payloadSequenceMutated = $true

    $dir = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $tmp = Join-Path $dir ('.' + (Split-Path -Leaf $Path) + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
    $json = $Payload | ConvertTo-Json -Depth 12
    [System.IO.File]::WriteAllText($tmp, $json, [System.Text.UTF8Encoding]::new($false))
    Move-RerunFileReplaceWithRetry -Source $tmp -Destination $Path -Label 'CSV rerun manifest'
    $tmp = ''
    $payloadSequenceCommitted = $true
    } finally {
        if ($payloadSequenceMutated -and -not $payloadSequenceCommitted) {
            if ($Payload -is [System.Collections.IDictionary]) {
                if ($payloadHadWriteSequence) {
                    $Payload['write_sequence'] = $payloadOriginalWriteSequence
                } else {
                    [void]$Payload.Remove('write_sequence')
                }
            } elseif ($payloadHadWriteSequence) {
                $Payload.write_sequence = $payloadOriginalWriteSequence
            } else {
                [void]$Payload.PSObject.Properties.Remove('write_sequence')
            }
        }
        if (-not [string]::IsNullOrWhiteSpace($tmp)) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
        if ($acquired -and $null -ne $mutex) {
            try { $mutex.ReleaseMutex() } catch {}
        }
        if ($null -ne $mutex) { $mutex.Dispose() }
    }
}

function Get-RerunJsonLineMutexName {
    param([Parameter(Mandatory)] [string]$Path)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes([System.IO.Path]::GetFullPath($Path).ToLowerInvariant())
        $hash = [System.BitConverter]::ToString($sha.ComputeHash($bytes)).Replace('-', '').Substring(0, 16)
        return "Global\MediaPipelineRerunCompletedManifest_$hash"
    } finally {
        if ($sha) { $sha.Dispose() }
    }
}

function Write-RerunJsonLineAppend {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] $Payload,
        [int]$Depth = 10
    )
    $mutex = $null
    $acquired = $false
    try {
        $dir = Split-Path -Parent $Path
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $mutex = [System.Threading.Mutex]::new($false, (Get-RerunJsonLineMutexName -Path $Path))
        $acquired = $mutex.WaitOne(2000)
        if (-not $acquired) { return $false }
        $line = $Payload | ConvertTo-Json -Depth $Depth -Compress
        [System.IO.File]::AppendAllText($Path, $line + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
        return $true
    } catch {
        Write-RerunLog "CSV rerun JSONL append failed for $Path : $($_.Exception.Message)" "WARN"
        return $false
    } finally {
        if ($acquired -and $null -ne $mutex) {
            try { $mutex.ReleaseMutex() } catch {}
        }
        if ($null -ne $mutex) { $mutex.Dispose() }
    }
}

function Add-RerunCompletedJobsManifestEntry {
    param(
        [Parameter(Mandatory)] [string]$OutputPath,
        [Parameter(Mandatory)] $Payload
    )
    if ([string]::IsNullOrWhiteSpace([string]$script:RerunCompletedJobsManifest)) {
        Write-RerunLog "Completed-jobs manifest append skipped; manifest path is unavailable for $OutputPath" "WARN"
        return $false
    }
    try {
        $entry = [ordered]@{}
        if ($Payload -is [System.Collections.IDictionary]) {
            foreach ($k in $Payload.Keys) { $entry[[string]$k] = $Payload[$k] }
        } else {
            foreach ($prop in @($Payload.PSObject.Properties)) { $entry[$prop.Name] = $prop.Value }
        }
        if (-not $entry.Contains('schema_version')) { $entry['schema_version'] = 'completed_job.v1' }
        $entry['output_path'] = $OutputPath
        $entry['output_file'] = Split-Path -Leaf $OutputPath
        if (-not $entry.Contains('job_id')) { $entry['job_id'] = '' }
        if (-not $entry.Contains('correlation_id')) { $entry['correlation_id'] = '' }
        $loggedAt = Get-Date -Format 'o'
        $entry['logged_at'] = $loggedAt
        if (-not $entry.Contains('created_at')) { $entry['created_at'] = $loggedAt }
        $entry['completed_manifest_source'] = 'csv_rerun_replace_final'
        $written = [bool](Write-RerunJsonLineAppend -Path ([string]$script:RerunCompletedJobsManifest) -Payload $entry -Depth 12)
        if (-not $written) {
            Write-RerunLog "Completed-jobs manifest append failed for $OutputPath : JSONL append lock unavailable or write failed" "WARN"
        }
        return $written
    } catch {
        Write-RerunLog "Completed-jobs manifest append failed for $OutputPath : $($_.Exception.Message)" "WARN"
        return $false
    }
}
