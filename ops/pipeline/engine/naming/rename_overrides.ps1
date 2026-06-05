# ==============================================================================
# ops\pipeline\engine\naming\rename_overrides.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\naming\naming.ps1. Keep function names stable;
# naming.ps1 dot-sources this file as the public compatibility surface.
# ==============================================================================

function Get-RenameOverrideSidecarPath {
    param([Parameter(Mandatory)] $File)

    $fullName = ''
    if ($File -and $File.PSObject.Properties['FullName']) {
        $fullName = [string]$File.FullName
    } else {
        $fullName = [string]$File
    }
    if ([string]::IsNullOrWhiteSpace($fullName)) { return '' }

    $dir = [System.IO.Path]::GetDirectoryName($fullName)
    $base = [System.IO.Path]::GetFileNameWithoutExtension($fullName)
    if ([string]::IsNullOrWhiteSpace($dir) -or [string]::IsNullOrWhiteSpace($base)) { return '' }
    return (Join-Path $dir ($base + '.mediapipeline.rename.json'))
}

function Get-RenameOverrideFinalName {
    param(
        [Parameter(Mandatory)] $File,
        [string]$Extension = ''
    )

    $sidecarPath = Get-RenameOverrideSidecarPath -File $File
    if ([string]::IsNullOrWhiteSpace($sidecarPath) -or -not (Test-Path -LiteralPath $sidecarPath -ErrorAction SilentlyContinue)) {
        return $null
    }

    try {
        $json = Get-Content -LiteralPath $sidecarPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $renameTool = $json.PSObject.Properties['RenameTool']
        if (-not $renameTool) { return $null }
        $payload = $renameTool.Value
        $forceProp = $payload.PSObject.Properties['ForcePipelineName']
        if (-not $forceProp -or -not [bool]$forceProp.Value) { return $null }
        $finalName = [string]$payload.FinalName
        if ([string]::IsNullOrWhiteSpace($finalName)) { return $null }
        $leaf = Split-Path -Leaf $finalName
        $base = [System.IO.Path]::GetFileNameWithoutExtension($leaf)
        if ([string]::IsNullOrWhiteSpace($base)) { return $null }
        $base = ($base -replace '[<>:"/\\|?*]', '' -replace '\s+', ' ').Trim()
        if ([string]::IsNullOrWhiteSpace($base)) { return $null }
        if (-not [string]::IsNullOrWhiteSpace($Extension) -and -not $Extension.StartsWith('.')) {
            $Extension = ".$Extension"
        }
        if ([string]::IsNullOrWhiteSpace($Extension)) {
            $Extension = [System.IO.Path]::GetExtension($leaf)
        }
        return [pscustomobject]@{
            SidecarPath = $sidecarPath
            FileBaseName = $base
            FileName = "$base$Extension"
        }
    } catch {
        if (Get-Command Write-Log -ErrorAction SilentlyContinue) {
            Write-Log "Rename override sidecar ignored for $sidecarPath : $($_.Exception.Message)" "WARN"
        }
        return $null
    }
}

function Apply-RenameOverrideToDestinationPlan {
    param(
        [Parameter(Mandatory)] $Plan,
        $File = $null,
        [string]$Extension = ''
    )

    if ($null -eq $File) { return $Plan }
    $override = Get-RenameOverrideFinalName -File $File -Extension $Extension
    if ($null -eq $override) { return $Plan }

    $Plan.FileBaseName = [string]$override.FileBaseName
    $Plan.FileName = [string]$override.FileName
    $Plan.SidecarBaseName = [string]$override.FileBaseName
    if ($Plan.PSObject.Properties['MediaKind'] -and [string]$Plan.MediaKind -eq 'Movie') {
        if ($Plan.PSObject.Properties['MovieTitle']) { $Plan.MovieTitle = [string]$override.FileBaseName }
        if ($Plan.PSObject.Properties['FolderName']) { $Plan.FolderName = [string]$override.FileBaseName }
        if ($Plan.PSObject.Properties['LibraryFolder'] -and -not [string]::IsNullOrWhiteSpace([string]$Plan.LibraryFolder)) {
            $Plan.RelativeDirectory = Join-PlexRelativePathParts @([string]$Plan.LibraryFolder, [string]$override.FileBaseName)
        } else {
            $Plan.RelativeDirectory = [string]$override.FileBaseName
        }
        if ($Plan.PSObject.Properties['IdentityKey']) { $Plan.IdentityKey = [string]$override.FileBaseName }
    }
    $Plan.RelativePath = Join-PlexRelativePathParts @([string]$Plan.RelativeDirectory, [string]$Plan.FileName)
    if (-not $Plan.PSObject.Properties['RenameOverrideApplied']) {
        $Plan | Add-Member -NotePropertyName 'RenameOverrideApplied' -NotePropertyValue $true
    } else {
        $Plan.RenameOverrideApplied = $true
    }
    if (-not $Plan.PSObject.Properties['RenameOverrideSidecar']) {
        $Plan | Add-Member -NotePropertyName 'RenameOverrideSidecar' -NotePropertyValue ([string]$override.SidecarPath)
    } else {
        $Plan.RenameOverrideSidecar = [string]$override.SidecarPath
    }
    return $Plan
}

