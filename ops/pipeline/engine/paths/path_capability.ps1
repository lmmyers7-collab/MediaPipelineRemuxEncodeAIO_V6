# ==============================================================================
# ops\pipeline\engine\paths\path_capability.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\paths\output_path_planning.ps1. Keep function names
# stable; output_path_planning.ps1 dot-sources this file as the public surface.
# ==============================================================================

function Test-MediaPipelinePathUnderRoot {
    param(
        [string] $Path,
        [string] $Root
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or [string]::IsNullOrWhiteSpace($Root)) { return $false }
    if (Get-Command -Name Test-MediaPipelinePathIsEqualOrChild -ErrorAction SilentlyContinue) {
        return Test-MediaPipelinePathIsEqualOrChild -Path $Path -Root $Root
    }
    try {
        $pathFull = [System.IO.Path]::GetFullPath($Path).TrimEnd('\','/')
        $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\','/')
        if ($pathFull.Equals($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
        return $pathFull.StartsWith($rootFull + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
    } catch {
        return $false
    }
}

function Test-PathComponentSupport {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [int] $MaxComponentLength = 255
    )

    try {
        [System.IO.Path]::GetFullPath($Path) | Out-Null
        $root = [System.IO.Path]::GetPathRoot($Path)
        $rest = if ($root -and $Path.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
            $Path.Substring($root.Length)
        } else {
            $Path
        }
        foreach ($segment in ($rest -split '[\\/]+')) {
            if ([string]::IsNullOrWhiteSpace($segment)) { continue }
            if ($segment.Length -gt $MaxComponentLength) {
                $preview = if ($segment.Length -gt 80) { $segment.Substring(0, 80) + '...' } else { $segment }
                return "path component is $($segment.Length) characters (limit $MaxComponentLength): $preview"
            }
        }
        return $null
    } catch {
        return "path is not valid: $($_.Exception.Message)"
    }
}

function Test-OutputPathCapability {
    param(
        [Parameter(Mandatory)] $Paths
    )

    $localOutputRoot = ''
    try {
        $localOutputRootValue = Get-Variable -Name LocalEncoded -Scope Script -ValueOnly -ErrorAction SilentlyContinue
        if ($null -ne $localOutputRootValue) { $localOutputRoot = [string]$localOutputRootValue }
    } catch {
        $localOutputRoot = ''
    }
    $serverOutputRoot = ''
    try {
        if ($Paths -is [System.Collections.IDictionary] -and $Paths.Contains('OutputRoot')) {
            $serverOutputRoot = [string]$Paths['OutputRoot']
        } elseif ($Paths -and $Paths.PSObject.Properties['OutputRoot']) {
            $serverOutputRoot = [string]$Paths.OutputRoot
        }
    } catch {
        $serverOutputRoot = ''
    }
    if ([string]::IsNullOrWhiteSpace($serverOutputRoot)) {
        try {
            $serverOutputRootValue = Get-Variable -Name Outsource -Scope Script -ValueOnly -ErrorAction SilentlyContinue
            if ($null -ne $serverOutputRootValue) { $serverOutputRoot = [string]$serverOutputRootValue }
        } catch {
            $serverOutputRoot = ''
        }
    }

    foreach ($target in @(
        @{ Label = 'local output';  Path = [string]$Paths.LocalOut;  Required = $true;  Root = $localOutputRoot },
        @{ Label = 'server output'; Path = [string]$Paths.ServerOut; Required = $false; Root = $serverOutputRoot }
    )) {
        $label = [string]$target.Label
        $path = [string]$target.Path
        $required = [bool]$target.Required
        $boundaryRoot = [string]$target.Root
        if ([string]::IsNullOrWhiteSpace($path)) {
            return @{ Ok = $false; Reason = "$label path is empty"; Path = $path }
        }

        $componentError = Test-PathComponentSupport -Path $path
        if ($componentError) {
            return @{ Ok = $false; Reason = "$label $componentError"; Path = $path }
        }

        $dir = Split-Path $path -Parent
        if ([string]::IsNullOrWhiteSpace($dir)) {
            return @{ Ok = $false; Reason = "$label has no parent directory"; Path = $path }
        }

        if (-not [string]::IsNullOrWhiteSpace($boundaryRoot) -and (Get-Command -Name Test-MediaPipelinePathBoundarySafe -ErrorAction SilentlyContinue)) {
            $boundary = Test-MediaPipelinePathBoundarySafe -Path $path -Root $boundaryRoot -AllowMissingLeaf
            if (-not [bool]$boundary.Ok) {
                if (-not $required -and [string]$boundary.ReasonCode -eq 'ROOT_MISSING') {
                    Write-Log "Output path preflight: $label configured root is missing/unavailable now. Publish/parking will handle this later. Root: $boundaryRoot" "WARN"
                    continue
                }
                $reason = "$label path is outside or unsafe for configured root ($($boundary.ReasonCode)): $($boundary.Reason)"
                return @{
                    Ok                 = $false
                    Reason             = $reason
                    Path               = $path
                    BoundaryRoot       = $boundaryRoot
                    BoundaryReasonCode = [string]$boundary.ReasonCode
                }
            }
        }

        $createdDir = $false
        $probe = $null
        try {
            if (-not (Test-Path -LiteralPath $dir -ErrorAction SilentlyContinue)) {
                New-Item -ItemType Directory -Path $dir -Force -ErrorAction Stop | Out-Null
                $createdDir = $true
            }
            $probe = Join-Path $dir (".mediapipeline-pathprobe." + [guid]::NewGuid().ToString("N") + ".tmp")
            [System.IO.File]::WriteAllText($probe, "probe", [System.Text.UTF8Encoding]::new($false))
            Remove-Item -LiteralPath $probe -Force -ErrorAction Stop
            $probe = $null
            if ($createdDir) {
                Remove-Item -LiteralPath $dir -Force -ErrorAction SilentlyContinue
            }
        } catch {
            if ($probe -and (Test-Path -LiteralPath $probe -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
            }
            if ($createdDir) {
                Remove-Item -LiteralPath $dir -Force -ErrorAction SilentlyContinue
            }
            $reason = "$label path is not writable/creatable now: $($_.Exception.Message)"
            if (-not $required) {
                Write-Log "Output path preflight: $reason. Publish/parking will handle this later." "WARN"
                continue
            }
            return @{ Ok = $false; Reason = $reason; Path = $path }
        }
    }

    return @{ Ok = $true; Reason = ''; Path = '' }
}
