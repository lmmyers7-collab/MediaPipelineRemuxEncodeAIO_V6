# ==============================================================================
# ops\pipeline\engine\shared\path_helpers.ps1
# ==============================================================================
# Pure path / string / version helpers extracted from MediaPipeline.ps1.
#
# This file is dot-sourced by engine stages and legacy shims so every function
# lives in the caller's scope. Extraction is purely a code-locality change with
# zero behavioural impact.
#
# Functions in here MUST stay free of shared state:
#   - no Write-Log calls
#   - no $script:* / $LogFile / $StopFlag references
#   - no native-process invocations
#
# Anything that needs logging or external state belongs in another module.
# ==============================================================================

function Test-IsUncPath {
    param([string]$Path)
    return (-not [string]::IsNullOrWhiteSpace($Path) -and ($Path.StartsWith('\\') -or $Path.StartsWith('//')))
}

function Get-UncShareRoot {
    param([string]$Path)
    if (-not (Test-IsUncPath $Path)) { return $null }
    $normalized = $Path -replace '/', '\'
    if ($normalized -match '^(\\\\[^\\]+\\[^\\]+)') {
        return ($Matches[1].TrimEnd('\') + '\')
    }
    return $null
}

function Get-MediaPipelineFilesystemBoundaryRoot {
    param([Parameter(Mandatory)] [string] $Path)

    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    $normalized = Normalize-MediaPipelinePathForBoundary $Path
    if ([string]::IsNullOrWhiteSpace($normalized)) { return '' }

    $root = ''
    try {
        $root = if (Test-IsUncPath $normalized) {
            [string](Get-UncShareRoot $normalized)
        } else {
            [string][System.IO.Path]::GetPathRoot($normalized)
        }
    } catch {
        return ''
    }
    if ([string]::IsNullOrWhiteSpace($root)) { return '' }
    return (Normalize-MediaPipelinePathForBoundary $root)
}

function Normalize-MediaPipelinePathForBoundary {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }

    $text = ([string]$Path).Trim()
    try {
        $text = [System.IO.Path]::GetFullPath($text)
    } catch {
    }
    $text = $text -replace '/', '\'

    try {
        $root = [System.IO.Path]::GetPathRoot($text)
        if (-not [string]::IsNullOrWhiteSpace($root)) {
            $rootText = ($root -replace '/', '\').TrimEnd('\')
            $trimmed = $text.TrimEnd('\')
            if ($trimmed.Equals($rootText, [System.StringComparison]::OrdinalIgnoreCase)) {
                return ($root -replace '/', '\')
            }
            return $trimmed
        }
    } catch {
    }

    return $text.TrimEnd('\')
}

function Test-MediaPipelinePathIsEqualOrChild {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string] $Root
    )

    $pathText = Normalize-MediaPipelinePathForBoundary $Path
    $rootText = Normalize-MediaPipelinePathForBoundary $Root
    if ([string]::IsNullOrWhiteSpace($pathText) -or [string]::IsNullOrWhiteSpace($rootText)) { return $false }

    $comparison = if ($IsWindows -or $env:OS -eq 'Windows_NT') {
        [System.StringComparison]::OrdinalIgnoreCase
    } else {
        [System.StringComparison]::Ordinal
    }

    if ($pathText.Equals($rootText, $comparison)) { return $true }
    return $pathText.StartsWith(($rootText.TrimEnd('\') + '\'), $comparison)
}

function New-MediaPipelinePathBoundaryResult {
    param(
        [bool] $Ok,
        [string] $ReasonCode,
        [string] $Reason,
        [string] $Path = '',
        [string] $Root = '',
        [string] $ReparsePath = ''
    )

    return [pscustomobject]@{
        Ok          = [bool]$Ok
        ReasonCode  = [string]$ReasonCode
        Reason      = [string]$Reason
        Path        = [string]$Path
        Root        = [string]$Root
        ReparsePath = [string]$ReparsePath
    }
}

function Test-MediaPipelinePathHasReparseAttribute {
    param([Parameter(Mandatory)] [string] $Path)

    try {
        $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
        return [bool]($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)
    } catch {
        throw [System.IO.IOException]::new("Unable to inspect path component attributes: $Path", $_.Exception)
    }
}

function Get-MediaPipelinePathInspection {
    param([Parameter(Mandatory)] [string] $Path)

    try {
        $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
        return [pscustomobject]@{
            Exists = $true
            Item = $item
        }
    } catch [System.Management.Automation.ItemNotFoundException] {
        return [pscustomobject]@{ Exists = $false; Item = $null }
    } catch [System.IO.FileNotFoundException] {
        return [pscustomobject]@{ Exists = $false; Item = $null }
    } catch [System.IO.DirectoryNotFoundException] {
        return [pscustomobject]@{ Exists = $false; Item = $null }
    } catch {
        throw [System.IO.IOException]::new("Unable to inspect path component: $Path", $_.Exception)
    }
}

function Get-MediaPipelineExistingPathChain {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string] $Root
    )

    $items = [System.Collections.Generic.List[string]]::new()
    $rootText = Normalize-MediaPipelinePathForBoundary $Root
    $pathText = Normalize-MediaPipelinePathForBoundary $Path
    if ([string]::IsNullOrWhiteSpace($rootText)) { return @() }
    $items.Add($rootText) | Out-Null
    $relative = Get-MediaPipelineRelativePath -Path $pathText -Root $rootText
    if ([string]::IsNullOrWhiteSpace($relative)) { return @($items.ToArray()) }

    $current = $rootText
    foreach ($part in ($relative -split '[\\/]')) {
        if ([string]::IsNullOrWhiteSpace($part)) { continue }
        $current = Join-Path $current $part
        $inspection = Get-MediaPipelinePathInspection -Path $current
        if ([bool]$inspection.Exists) {
            $items.Add((Normalize-MediaPipelinePathForBoundary $current)) | Out-Null
        } else {
            break
        }
    }
    return @($items.ToArray())
}

function Test-MediaPipelinePathBoundarySafe {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string] $Root,
        [switch] $AllowMissingLeaf,
        [switch] $AllowRootTarget
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return (New-MediaPipelinePathBoundaryResult -Ok $false -ReasonCode 'EMPTY_PATH' -Reason 'path is empty' -Path $Path -Root $Root)
    }
    if ([string]::IsNullOrWhiteSpace($Root)) {
        return (New-MediaPipelinePathBoundaryResult -Ok $false -ReasonCode 'EMPTY_ROOT' -Reason 'root is empty' -Path $Path -Root $Root)
    }

    $pathText = Normalize-MediaPipelinePathForBoundary $Path
    $rootText = Normalize-MediaPipelinePathForBoundary $Root
    if (-not (Test-MediaPipelinePathIsEqualOrChild -Path $pathText -Root $rootText)) {
        return (New-MediaPipelinePathBoundaryResult -Ok $false -ReasonCode 'OUTSIDE_ALLOWED_ROOT' -Reason 'path is outside allowed root' -Path $pathText -Root $rootText)
    }
    if (-not $AllowRootTarget -and $pathText.Equals($rootText, [System.StringComparison]::OrdinalIgnoreCase)) {
        return (New-MediaPipelinePathBoundaryResult -Ok $false -ReasonCode 'ROOT_MUTATION_TARGET' -Reason 'path is the allowed root itself' -Path $pathText -Root $rootText)
    }
    try {
        $rootInspection = Get-MediaPipelinePathInspection -Path $rootText
    } catch {
        return (New-MediaPipelinePathBoundaryResult -Ok $false -ReasonCode 'REPARSE_INSPECTION_FAILED' -Reason "allowed-root inspection failed: $($_.Exception.Message)" -Path $pathText -Root $rootText)
    }
    if (-not [bool]$rootInspection.Exists) {
        return (New-MediaPipelinePathBoundaryResult -Ok $false -ReasonCode 'ROOT_MISSING' -Reason 'allowed root does not exist' -Path $pathText -Root $rootText)
    }
    if (-not ($rootInspection.Item -is [System.IO.DirectoryInfo])) {
        return (New-MediaPipelinePathBoundaryResult -Ok $false -ReasonCode 'ROOT_NOT_DIRECTORY' -Reason 'allowed root is not a directory' -Path $pathText -Root $rootText)
    }
    if (-not $AllowMissingLeaf) {
        try {
            $pathInspection = Get-MediaPipelinePathInspection -Path $pathText
        } catch {
            return (New-MediaPipelinePathBoundaryResult -Ok $false -ReasonCode 'REPARSE_INSPECTION_FAILED' -Reason "target-path inspection failed: $($_.Exception.Message)" -Path $pathText -Root $rootText)
        }
        if (-not [bool]$pathInspection.Exists) {
            return (New-MediaPipelinePathBoundaryResult -Ok $false -ReasonCode 'PATH_MISSING' -Reason 'path does not exist' -Path $pathText -Root $rootText)
        }
    }

    try {
        foreach ($candidate in (Get-MediaPipelineExistingPathChain -Path $pathText -Root $rootText)) {
            if (Test-MediaPipelinePathHasReparseAttribute -Path $candidate) {
                return (New-MediaPipelinePathBoundaryResult -Ok $false -ReasonCode 'REPARSE_POINT_COMPONENT' -Reason 'path contains a symlink, junction, or reparse point component' -Path $pathText -Root $rootText -ReparsePath $candidate)
            }
        }
    } catch {
        return (New-MediaPipelinePathBoundaryResult -Ok $false -ReasonCode 'REPARSE_INSPECTION_FAILED' -Reason "path reparse inspection failed: $($_.Exception.Message)" -Path $pathText -Root $rootText)
    }

    return (New-MediaPipelinePathBoundaryResult -Ok $true -ReasonCode 'OK' -Reason 'path is within root and has no reparse components' -Path $pathText -Root $rootText)
}

function Test-MediaPipelinePathHasReparsePoint {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [string] $Root = ''
    )

    $rootText = if ([string]::IsNullOrWhiteSpace($Root)) {
        $parent = Split-Path -Parent $Path
        if ([string]::IsNullOrWhiteSpace($parent)) { $Path } else { $parent }
    } else {
        $Root
    }
    $result = Test-MediaPipelinePathBoundarySafe -Path $Path -Root $rootText -AllowMissingLeaf -AllowRootTarget
    return (-not $result.Ok -and $result.ReasonCode -eq 'REPARSE_POINT_COMPONENT')
}

function Get-MediaPipelineRelativePath {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string] $Root
    )

    if (-not (Test-MediaPipelinePathIsEqualOrChild -Path $Path -Root $Root)) { return $null }
    try {
        $relative = [System.IO.Path]::GetRelativePath(
            (Normalize-MediaPipelinePathForBoundary $Root),
            (Normalize-MediaPipelinePathForBoundary $Path)
        )
        if ([string]::IsNullOrWhiteSpace($relative) -or $relative -eq '.') { return '' }
        if ($relative -match '^\.\.(\\|/|$)') { return $null }
        return $relative.TrimStart('\', '/')
    } catch {
        $pathText = Normalize-MediaPipelinePathForBoundary $Path
        $rootText = Normalize-MediaPipelinePathForBoundary $Root
        if ($pathText.Equals($rootText, [System.StringComparison]::OrdinalIgnoreCase)) { return '' }
        return $pathText.Substring($rootText.Length).TrimStart('\', '/')
    }
}

function Resolve-SingleFileMediaKind {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [string] $SourceMovies = '',
        [string] $SourceTV = ''
    )

    if (Get-Command -Name Get-MediaPipelineLibraryProfileForPath -ErrorAction SilentlyContinue) {
        $profile = Get-MediaPipelineLibraryProfileForPath -SourcePath $Path
        if ($profile) {
            $designation = ''
            $sourceRoot = ''
            if (Get-Command -Name Get-MediaPipelineProfileProperty -ErrorAction SilentlyContinue) {
                $designation = ([string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'designation' -Default '')).Trim().ToLowerInvariant()
                $sourceRoot = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'source_path' -Default '')
            }
            if ($designation -in @('movie','tv')) {
                return [pscustomobject]@{
                    MediaKind = $designation
                    IsTV      = ($designation -eq 'tv')
                    Reason    = 'library_profile_designation'
                    Root      = if ([string]::IsNullOrWhiteSpace($sourceRoot)) { '' } else { Normalize-MediaPipelinePathForBoundary $sourceRoot }
                }
            }
        }
    }

    $bestRootMatch = $null
    foreach ($candidate in @(
        @{ MediaKind = 'tv';    Root = $SourceTV;     Reason = 'source_tv_root' },
        @{ MediaKind = 'movie'; Root = $SourceMovies; Reason = 'source_movies_root' }
    )) {
        $rootText = [string]$candidate.Root
        if ([string]::IsNullOrWhiteSpace($rootText)) { continue }
        if (-not (Test-MediaPipelinePathIsEqualOrChild -Path $Path -Root $rootText)) { continue }

        $normalizedRoot = Normalize-MediaPipelinePathForBoundary $rootText
        $match = [pscustomobject]@{
            MediaKind = [string]$candidate.MediaKind
            IsTV      = ([string]$candidate.MediaKind -eq 'tv')
            Reason    = [string]$candidate.Reason
            Root      = $normalizedRoot
        }

        if ($null -eq $bestRootMatch -or
            $normalizedRoot.Length -gt ([string]$bestRootMatch.Root).Length -or
            ($normalizedRoot.Length -eq ([string]$bestRootMatch.Root).Length -and $match.IsTV)) {
            $bestRootMatch = $match
        }
    }

    if ($null -ne $bestRootMatch) { return $bestRootMatch }

    $looksLikeTv = (
        $Path -match '(?i)[/\\]Season\s+\d+[/\\]' -or
        $Path -match '(?i)(?<!\d)S\d{1,2}E\d{1,3}(?!\d)'
    )
    if ($looksLikeTv) {
        return [pscustomobject]@{
            MediaKind = 'tv'
            IsTV      = $true
            Reason    = 'tv_path_pattern'
            Root      = ''
        }
    }

    return [pscustomobject]@{
        MediaKind = 'movie'
        IsTV      = $false
        Reason    = 'default_movie'
        Root      = ''
    }
}

function Format-CommandArgument {
    param([string]$Value)
    if ($null -eq $Value) { return '""' }
    if ($Value -eq '') { return '""' }
    if ($Value -notmatch '[\s"`]') { return $Value }

    $escaped = $Value -replace '(\\*)"', '$1$1\"'
    $escaped = $escaped -replace '([\\]+)$', '$1$1'
    return '"' + $escaped + '"'
}

function Format-NativeCommandLine {
    param(
        [string]$FilePath,
        [array]$ArgumentList
    )
    $parts = [System.Collections.Generic.List[string]]::new()
    $parts.Add((Format-CommandArgument $FilePath))
    foreach ($arg in $ArgumentList) {
        $parts.Add((Format-CommandArgument ([string]$arg)))
    }
    return ($parts -join ' ')
}

# FIX#13: accept 1-3 digit millisecond fields. The old regex demanded
# \d{2,3} and silently returned 0 for timestamps like "00:00:12,1" or
# "00:00:12,01", which caused ConvertTo-Milliseconds-based gap
# calculations in Merge-AdjacentIdenticalCues to compute a huge
# negative gap and spuriously merge unrelated cues.
function ConvertTo-Milliseconds {
    param([string]$Timestamp)
    if ($Timestamp -match '^(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})') {
        # Left-pad the ms field to exactly 3 digits so "1" -> "100",
        # "01" -> "010", "001" -> "001". That matches SRT semantics
        # (the fractional field is a 3-digit millisecond number).
        $msField = $Matches[4].PadRight(3, '0').Substring(0, 3)
        return ([int]$Matches[1]*3600000) + ([int]$Matches[2]*60000) +
               ([int]$Matches[3]*1000)   + [int]$msField
    }
    return 0
}

# Returns $true if $A is strictly less than $B (semver-ish, up to 3 parts).
function Compare-PipelineVersion {
    param([string]$A, [string]$B)
    $pa = ($A -split '\.') + @('0','0','0') | Select-Object -First 3 | ForEach-Object { [int]$_ }
    $pb = ($B -split '\.') + @('0','0','0') | Select-Object -First 3 | ForEach-Object { [int]$_ }
    for ($i = 0; $i -lt 3; $i++) {
        if ($pa[$i] -lt $pb[$i]) { return $true  }
        if ($pa[$i] -gt $pb[$i]) { return $false }
    }
    return $false
}

function Test-PipelineVersionString {
    param([string]$Value)
    return ($Value -match '^\d+(\.\d+){0,2}$')
}
