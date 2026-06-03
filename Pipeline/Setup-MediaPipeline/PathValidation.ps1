# Dot-sourced helper slice for Setup-MediaPipeline.ps1. Keep CLI orchestration in the parent script.

function Test-PathWritable {
    param([string]$Path)
    $probe = Join-Path $Path ".__mp_write_test_$([guid]::NewGuid().ToString('N')).tmp"
    try {
        Set-Content -LiteralPath $probe -Value 'probe' -Encoding UTF8 -ErrorAction Stop
        Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
        return $true
    } catch {
        return $false
    }
}

function ConvertTo-PowerShellLiteralString {
    param([AllowNull()][string]$Value)

    if ($null -eq $Value) { return '$null' }
    return "'" + ([string]$Value -replace "'", "''") + "'"
}

function Test-ValidationPathExists {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [int]$TimeoutSeconds = 12
    )

    $pathLiteral = ConvertTo-PowerShellLiteralString -Value $Path
    $command = @"
`$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $pathLiteral) { exit 0 }
exit 2
"@
    $result = Invoke-SetupValidationProbe -Command $command -TimeoutSeconds $TimeoutSeconds
    return [pscustomobject]@{
        Exists = ($result.ExitCode -eq 0)
        TimedOut = $result.TimedOut
        StartError = $result.StartError
        Output = $result.Output
    }
}

function Test-ValidationPathWritable {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [int]$TimeoutSeconds = 12
    )

    $pathLiteral = ConvertTo-PowerShellLiteralString -Value $Path
    $command = @"
`$ErrorActionPreference = 'Stop'
`$path = $pathLiteral
if (-not (Test-Path -LiteralPath `$path -PathType Container)) { exit 2 }
`$probe = Join-Path `$path ('.__mp_write_test_' + [guid]::NewGuid().ToString('N') + '.tmp')
try {
    Set-Content -LiteralPath `$probe -Value 'probe' -Encoding UTF8 -ErrorAction Stop
    Remove-Item -LiteralPath `$probe -Force -ErrorAction SilentlyContinue
    exit 0
} catch {
    Write-Output `$_.Exception.Message
    if (Test-Path -LiteralPath `$probe) {
        Remove-Item -LiteralPath `$probe -Force -ErrorAction SilentlyContinue
    }
    exit 1
}
"@
    $result = Invoke-SetupValidationProbe -Command $command -TimeoutSeconds $TimeoutSeconds
    return [pscustomobject]@{
        Writable = ($result.ExitCode -eq 0)
        Missing = ($result.ExitCode -eq 2)
        TimedOut = $result.TimedOut
        StartError = $result.StartError
        Output = $result.Output
    }
}

function Read-Path {
    param(
        [string]$Prompt,
        [string]$Default,
        [switch]$CreateIfMissing,
        [switch]$MustBeWritable,
        [bool]$CreateDefaultYes = $true
    )

    while ($true) {
        $rawPath = Read-WithDefault $Prompt $Default
        $path = Normalize-UserPath -Path $rawPath -BasePath $script:ScriptDir
        if ([string]::IsNullOrWhiteSpace($path)) {
            Write-Warn "Path cannot be empty."
            continue
        }

        $exists = Test-Path -LiteralPath $path -ErrorAction SilentlyContinue
        if (-not $exists -and $CreateIfMissing) {
            if (Read-YesNo "Create missing folder '$path' now?" -DefaultYes $CreateDefaultYes) {
                try {
                    New-Item -ItemType Directory -Path $path -Force | Out-Null
                    Write-Ok "Created $path"
                    $exists = $true
                } catch {
                    Write-Fail "Could not create $path : $_"
                    continue
                }
            } else {
                Write-Warn "Folder must exist before deployment can use it."
                if ($script:UseAcceptDefaults) {
                    Write-Warn "Keeping missing path for validation failure: $path"
                    return $path
                }
                continue
            }
        }

        if (-not $exists) {
            Write-Warn "Path does not exist yet: $path"
            if ($script:UseAcceptDefaults) {
                return $path
            }
            if (-not (Read-YesNo "Keep this path anyway?" -DefaultYes $false)) {
                continue
            }
        }

        if ($MustBeWritable -and $exists -and -not (Test-PathWritable $path)) {
            Write-Fail "Path is not writable: $path"
            if ($script:UseAcceptDefaults) {
                Write-Warn "Keeping non-writable path for validation failure: $path"
                return $path
            }
            continue
        }

        if ($path -ne $rawPath.Trim().Trim('"').Trim("'")) {
            Write-Info "Normalized path: $path"
        }

        return $path
    }
}

function Test-PathsDisjoint {
    param([hashtable]$Paths)
    $normalized = @{}
    foreach ($key in $Paths.Keys) {
        $raw = $Paths[$key]
        if ([string]::IsNullOrWhiteSpace($raw)) { continue }
        try {
            $full = [System.IO.Path]::GetFullPath($raw).TrimEnd('\','/').ToLowerInvariant()
        } catch {
            $full = $raw.TrimEnd('\','/').ToLowerInvariant()
        }
        $normalized[$key] = $full
    }

    $keys = @($normalized.Keys)
    for ($i = 0; $i -lt $keys.Count; $i++) {
        for ($j = $i + 1; $j -lt $keys.Count; $j++) {
            $a = $keys[$i]
            $b = $keys[$j]
            if ($normalized[$a] -eq $normalized[$b]) {
                throw "$a and $b resolve to the same path."
            }
            $ap = $normalized[$a] + [IO.Path]::DirectorySeparatorChar
            $bp = $normalized[$b] + [IO.Path]::DirectorySeparatorChar
            if ($ap.StartsWith($bp) -or $bp.StartsWith($ap)) {
                throw "$a and $b are nested. Keep source, scratch, and outsource folders separate."
            }
        }
    }
}
