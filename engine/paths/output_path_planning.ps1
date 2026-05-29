# ==============================================================================
# engine\paths\output_path_planning.ps1
# ==============================================================================
# Output destination planning and path capability checks.
#
# Dot-sourced by the engine entrypoints and legacy compatibility loaders. These
# helpers read path and naming configuration from script scope at call time.
# ==============================================================================

function Get-OutputPaths {
    param($File, [bool]$isTV, $tvInfo, [string]$SafeName)
    if ($isTV) {
        $plan = New-PlexDestinationPlan -MediaKind 'TV' -File $File -TvInfo $tvInfo -OriginalName $tvInfo.OriginalName -Extension $OutputContainer -IncludeLibraryFolder:$CreateTVSubfolder
    } else {
        $plan = New-PlexDestinationPlan -MediaKind 'Movie' -File $File -OriginalName $File.Name -Extension $OutputContainer
    }

    $localDir  = Join-Path $LocalEncoded $plan.RelativeDirectory
    $serverDir = Join-Path $Outsource    $plan.RelativeDirectory
    return @{
        LocalDir=$localDir; LocalOut=Join-Path $localDir $plan.FileName
        ServerDir=$serverDir; ServerOut=Join-Path $serverDir $plan.FileName
        PlexPlan=$plan; RelativePath=$plan.RelativePath
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

    foreach ($target in @(
        @{ Label = 'local output';  Path = [string]$Paths.LocalOut;  Required = $true },
        @{ Label = 'server output'; Path = [string]$Paths.ServerOut; Required = $false }
    )) {
        $label = [string]$target.Label
        $path = [string]$target.Path
        $required = [bool]$target.Required
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
