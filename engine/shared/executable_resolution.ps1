# ==============================================================================
# engine\shared\executable_resolution.ps1
# ==============================================================================
# Portable runtime tool discovery helpers.
#
# Dot-sourced by callers. Resolve-BundledExecutable reads $scriptDir and
# $script:AllowSystemTools at call time, so the module can load before
# configuration while preserving the existing startup order.
# ==============================================================================

function Resolve-BundledExecutable {
    param(
        [Parameter(Mandatory = $true)][string]$CommandName,
        [string[]]$RelativeCandidates = @()
    )

    foreach ($relative in $RelativeCandidates) {
        $candidate = Join-Path $scriptDir $relative
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    if (-not $script:AllowSystemTools) {
        return $null
    }

    foreach ($cmd in @(Get-Command $CommandName -All -ErrorAction SilentlyContinue)) {
        if (-not ($cmd -and $cmd.Source)) {
            continue
        }
        if ($CommandName -eq 'python' -and $cmd.Source -match '\\WindowsApps\\') {
            continue
        }
        return $cmd.Source
    }

    return $null
}
