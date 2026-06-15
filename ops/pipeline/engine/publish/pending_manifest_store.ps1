# ==============================================================================
# ops\pipeline\engine\publish\pending_manifest_store.ps1
# ==============================================================================
# Manifest accessors and persistence helpers for PendingServerPush.
#
# Dot-sourced before PendingPush.ps1. This module intentionally keeps the same
# function names that PendingPush.ps1 used internally, so the extraction is a
# locality/testability change and not a behavior change.
# ==============================================================================

function Get-PendingObjectProperty {
    param(
        $Object,
        [Parameter(Mandatory)] [string] $Name
    )

    if ($null -eq $Object) { return $null }
    if ($Object -is [System.Collections.Specialized.OrderedDictionary] -and $Object.Contains($Name)) {
        return $Object[$Name]
    }
    if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($Name)) {
        return $Object[$Name]
    }
    $prop = $Object.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $null
}

function Get-PendingSidecarEntries {
    param($Manifest)

    $value = Get-PendingObjectProperty -Object $Manifest -Name 'sidecar_files'
    if ($null -eq $value) { return @() }
    return @($value | Where-Object { $null -ne $_ })
}

# PSCustomObject (from ConvertFrom-Json) -> ordered hashtable. Lets callers
# round-trip a parsed manifest, tweak fields, and re-serialise without losing key
# ordering. ConvertTo-Json on an [ordered] preserves field order in the output
# JSON; on a plain PSCustomObject it does not.
function ConvertTo-PendingManifestMap {
    param($Manifest)
    $map = [ordered]@{}
    if ($Manifest) {
        foreach ($prop in $Manifest.PSObject.Properties) {
            $map[$prop.Name] = $prop.Value
        }
    }
    return $map
}

function Read-PendingManifestFile {
    param([Parameter(Mandatory)] [string] $Path)

    return (Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop)
}

function Test-PendingObjectHasProperty {
    param(
        $Object,
        [Parameter(Mandatory)] [string] $Name
    )

    if ($null -eq $Object) { return $false }
    if ($Object -is [System.Collections.IDictionary]) {
        return $Object.Contains($Name)
    }
    return ($null -ne $Object.PSObject.Properties[$Name])
}

function Get-PendingManifestText {
    param(
        $Object,
        [Parameter(Mandatory)] [string] $Name
    )

    $value = Get-PendingObjectProperty -Object $Object -Name $Name
    if ($null -eq $value) { return '' }
    return [string]$value
}

function Get-PendingScriptVariableText {
    param([Parameter(Mandatory)] [string] $Name)

    try {
        $value = Get-Variable -Name $Name -Scope Script -ValueOnly -ErrorAction SilentlyContinue
        if ($null -eq $value) { return '' }
        return [string]$value
    } catch {
        return ''
    }
}

function New-PendingManifestTrustResult {
    param(
        [bool] $Ok,
        [string] $ReasonCode,
        [string] $Reason,
        [string] $Status = 'invalid_manifest',
        [string] $ManifestPath = '',
        [string] $LocalFile = '',
        [string] $ServerOut = '',
        [string] $SourcePath = ''
    )

    return [pscustomobject]@{
        Ok           = [bool]$Ok
        ReasonCode   = [string]$ReasonCode
        Reason       = [string]$Reason
        Status       = [string]$Status
        ManifestPath = [string]$ManifestPath
        LocalFile    = [string]$LocalFile
        ServerOut    = [string]$ServerOut
        SourcePath   = [string]$SourcePath
    }
}

function Get-PendingManifestFilePathText {
    param($ManifestFile)

    if ($ManifestFile -is [System.IO.FileInfo]) { return [string]$ManifestFile.FullName }
    return [string]$ManifestFile
}

function Test-PendingManifestPathBoundary {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string] $Root,
        [switch] $AllowMissingLeaf,
        [switch] $AllowRootTarget
    )

    if (Get-Command -Name Test-MediaPipelinePathBoundarySafe -ErrorAction SilentlyContinue) {
        return Test-MediaPipelinePathBoundarySafe -Path $Path -Root $Root -AllowMissingLeaf:$AllowMissingLeaf -AllowRootTarget:$AllowRootTarget
    }

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return [pscustomobject]@{ Ok = $false; ReasonCode = 'EMPTY_PATH'; Reason = 'path is empty'; Path = $Path; Root = $Root }
    }
    if ([string]::IsNullOrWhiteSpace($Root)) {
        return [pscustomobject]@{ Ok = $false; ReasonCode = 'EMPTY_ROOT'; Reason = 'root is empty'; Path = $Path; Root = $Root }
    }
    $inside = if (Get-Command -Name Test-MediaPipelinePathIsEqualOrChild -ErrorAction SilentlyContinue) {
        Test-MediaPipelinePathIsEqualOrChild -Path $Path -Root $Root
    } else {
        $pathFull = [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
        $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
        $pathFull.Equals($rootFull, [System.StringComparison]::OrdinalIgnoreCase) -or
            $pathFull.StartsWith($rootFull + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
    }
    if (-not $inside) {
        return [pscustomobject]@{ Ok = $false; ReasonCode = 'OUTSIDE_ALLOWED_ROOT'; Reason = 'path is outside allowed root'; Path = $Path; Root = $Root }
    }
    if (-not $AllowRootTarget -and $Path.TrimEnd('\', '/').Equals($Root.TrimEnd('\', '/'), [System.StringComparison]::OrdinalIgnoreCase)) {
        return [pscustomobject]@{ Ok = $false; ReasonCode = 'ROOT_MUTATION_TARGET'; Reason = 'path is the allowed root itself'; Path = $Path; Root = $Root }
    }
    if (-not $AllowMissingLeaf -and -not (Test-Path -LiteralPath $Path -ErrorAction SilentlyContinue)) {
        return [pscustomobject]@{ Ok = $false; ReasonCode = 'PATH_MISSING'; Reason = 'path does not exist'; Path = $Path; Root = $Root }
    }
    return [pscustomobject]@{ Ok = $true; ReasonCode = 'OK'; Reason = 'path is inside root'; Path = $Path; Root = $Root }
}

function Get-PendingManifestConfiguredOutputRoot {
    param($Manifest)

    $sourcePath = Get-PendingManifestText -Object $Manifest -Name 'source_path'
    if (Get-Command -Name Get-MediaPipelineLibraryOutputRootForPath -ErrorAction SilentlyContinue) {
        try {
            $profileOutputRoot = [string](Get-MediaPipelineLibraryOutputRootForPath -SourcePath $sourcePath)
            if (-not [string]::IsNullOrWhiteSpace($profileOutputRoot)) { return $profileOutputRoot }
        } catch {
        }
    }
    return (Get-PendingScriptVariableText -Name 'Outsource')
}

function Get-PendingManifestConfiguredSourceRoots {
    $roots = [System.Collections.Generic.List[string]]::new()
    foreach ($name in @('SourceMovies', 'SourceTV')) {
        $value = Get-PendingScriptVariableText -Name $name
        if (-not [string]::IsNullOrWhiteSpace($value)) { $roots.Add($value) | Out-Null }
    }
    if (Get-Command -Name Get-MediaPipelineLibraryProfiles -ErrorAction SilentlyContinue) {
        try {
            foreach ($profile in @(Get-MediaPipelineLibraryProfiles)) {
                $sourceRoot = ''
                if (Get-Command -Name Get-MediaPipelineProfileProperty -ErrorAction SilentlyContinue) {
                    $sourceRoot = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'source_path' -Default '')
                } else {
                    $sourceRoot = [string](Get-PendingObjectProperty -Object $profile -Name 'source_path')
                }
                if (-not [string]::IsNullOrWhiteSpace($sourceRoot)) { $roots.Add($sourceRoot) | Out-Null }
            }
        } catch {
        }
    }
    return @($roots.ToArray() | Select-Object -Unique)
}

function Test-PendingManifestPathUnderRoot {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string] $Root
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or [string]::IsNullOrWhiteSpace($Root)) { return $false }
    if (Get-Command -Name Test-MediaPipelinePathIsEqualOrChild -ErrorAction SilentlyContinue) {
        return Test-MediaPipelinePathIsEqualOrChild -Path $Path -Root $Root
    }
    try {
        $pathFull = [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
        $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
        return ($pathFull.Equals($rootFull, [System.StringComparison]::OrdinalIgnoreCase) -or
            $pathFull.StartsWith($rootFull + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase))
    } catch {
        return $false
    }
}

function Test-PendingManifestPathOutsideForbiddenRoots {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [array] $Roots = @(),
        [Parameter(Mandatory)] [string] $Label,
        [string] $ManifestPath = '',
        [string] $LocalFile = '',
        [string] $ServerOut = '',
        [string] $SourcePath = ''
    )

    foreach ($root in @($Roots)) {
        $rootText = [string]$root
        if ([string]::IsNullOrWhiteSpace($rootText)) { continue }
        if (Test-PendingManifestPathUnderRoot -Path $Path -Root $rootText) {
            return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'FORBIDDEN_ROOT' -Reason "$Label is under forbidden root: $rootText" -Status 'invalid_manifest' -ManifestPath $ManifestPath -LocalFile $LocalFile -ServerOut $ServerOut -SourcePath $SourcePath
        }
    }
    return New-PendingManifestTrustResult -Ok:$true -ReasonCode 'OK' -Reason 'ok' -ManifestPath $ManifestPath -LocalFile $LocalFile -ServerOut $ServerOut -SourcePath $SourcePath
}

function Test-PendingManifestCurrentContractFields {
    param(
        [Parameter(Mandatory)] $Manifest,
        [string] $ManifestPath = ''
    )

    $localFile = Get-PendingManifestText -Object $Manifest -Name 'local_file'
    $serverOut = Get-PendingManifestText -Object $Manifest -Name 'server_out'
    $sourcePath = Get-PendingManifestText -Object $Manifest -Name 'source_path'

    $schemaVersion = Get-PendingManifestText -Object $Manifest -Name 'schema_version'
    if ([string]::IsNullOrWhiteSpace($schemaVersion)) {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'LEGACY_MANIFEST' -Reason 'Legacy pending manifest without schema_version cannot be drained or repaired automatically.' -Status 'invalid_manifest' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }
    if ($schemaVersion -ne 'pending_push_manifest.v1') {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'SCHEMA_VERSION_MISMATCH' -Reason "schema_version must be pending_push_manifest.v1; got $schemaVersion" -Status 'invalid_manifest' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }

    foreach ($key in @(
        'pipeline_version',
        'publish_transaction_id',
        'manifest_state',
        'route',
        'local_file',
        'server_out',
        'source_identity_v2',
        'source_identity_v2_algorithm',
        'source_path'
    )) {
        $value = Get-PendingManifestText -Object $Manifest -Name $key
        if ([string]::IsNullOrWhiteSpace($value)) {
            return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'REQUIRED_FIELD_MISSING' -Reason "$key is missing or blank in current pending manifest." -Status 'invalid_manifest' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
        }
    }

    $outputSize = Get-PendingObjectProperty -Object $Manifest -Name 'output_size'
    if ($null -eq $outputSize) {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'OUTPUT_SIZE_MISSING' -Reason 'output_size is missing in current pending manifest.' -Status 'invalid_manifest' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }
    try {
        if ([long]$outputSize -lt 0) {
            return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'OUTPUT_SIZE_INVALID' -Reason 'output_size is negative in current pending manifest.' -Status 'invalid_manifest' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
        }
    } catch {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'OUTPUT_SIZE_INVALID' -Reason 'output_size is not an integer in current pending manifest.' -Status 'invalid_manifest' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }

    foreach ($key in @(
        'sidecar_files',
        'tx3g_srt_tracks',
        'tx3g_srt_failures',
        'bdpgs_srt_failures',
        'vobsub_srt_failures',
        'tx3g_embedded_srt_tracks',
        'bdpgs_embedded_srt_tracks',
        'vobsub_embedded_srt_tracks'
    )) {
        if (-not (Test-PendingObjectHasProperty -Object $Manifest -Name $key)) {
            return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'REQUIRED_ARRAY_MISSING' -Reason "$key is missing in current pending manifest." -Status 'invalid_manifest' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
        }
        $value = Get-PendingObjectProperty -Object $Manifest -Name $key
        if ($null -ne $value -and ($value -is [string] -or ($value -isnot [System.Array] -and $value -isnot [System.Collections.IEnumerable]))) {
            return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'REQUIRED_ARRAY_INVALID' -Reason "$key must be an array in current pending manifest." -Status 'invalid_manifest' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
        }
    }

    return New-PendingManifestTrustResult -Ok:$true -ReasonCode 'OK' -Reason 'ok' -Status 'trusted' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
}

function Test-PendingManifestDestinationTrusted {
    param(
        [Parameter(Mandatory)] $Manifest,
        [string] $ManifestPath = ''
    )

    $localFile = Get-PendingManifestText -Object $Manifest -Name 'local_file'
    $serverOut = Get-PendingManifestText -Object $Manifest -Name 'server_out'
    $sourcePath = Get-PendingManifestText -Object $Manifest -Name 'source_path'
    $outputRoot = Get-PendingManifestConfiguredOutputRoot -Manifest $Manifest
    if ([string]::IsNullOrWhiteSpace($outputRoot)) {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'OUTPUT_ROOT_MISSING' -Reason 'Configured output root is missing; server_out cannot be trusted.' -Status 'invalid_manifest' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }
    $serverBoundary = Test-PendingManifestPathBoundary -Path $serverOut -Root $outputRoot -AllowMissingLeaf
    if (-not $serverBoundary.Ok) {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode "SERVER_OUT_$($serverBoundary.ReasonCode)" -Reason "server_out is not inside the configured output root ($($serverBoundary.ReasonCode)): $serverOut" -Status 'invalid_manifest' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }

    $forbiddenRoots = [System.Collections.Generic.List[string]]::new()
    foreach ($root in @(Get-PendingManifestConfiguredSourceRoots)) { if ($root) { $forbiddenRoots.Add([string]$root) | Out-Null } }
    foreach ($name in @('LocalBase', 'LocalPendingPush')) {
        $value = Get-PendingScriptVariableText -Name $name
        if (-not [string]::IsNullOrWhiteSpace($value)) { $forbiddenRoots.Add($value) | Out-Null }
    }
    $forbidden = Test-PendingManifestPathOutsideForbiddenRoots -Path $serverOut -Roots @($forbiddenRoots.ToArray()) -Label 'server_out' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    if (-not $forbidden.Ok) { return $forbidden }

    return New-PendingManifestTrustResult -Ok:$true -ReasonCode 'OK' -Reason 'ok' -Status 'trusted' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
}

function Test-PendingSidecarTrustedForPublish {
    param(
        [Parameter(Mandatory)] $Manifest,
        [Parameter(Mandatory)] $Sidecar,
        [string] $ManifestPath = '',
        [switch] $AllowMissingLocal
    )

    $localFile = Get-PendingManifestText -Object $Manifest -Name 'local_file'
    $serverOut = Get-PendingManifestText -Object $Manifest -Name 'server_out'
    $sourcePath = Get-PendingManifestText -Object $Manifest -Name 'source_path'
    $pendingRoot = Get-PendingScriptVariableText -Name 'LocalPendingPush'
    $sidecarLocal = Get-PendingManifestText -Object $Sidecar -Name 'local_file'
    $sidecarServer = Get-PendingManifestText -Object $Sidecar -Name 'server_out'
    if ([string]::IsNullOrWhiteSpace($sidecarLocal) -or [string]::IsNullOrWhiteSpace($sidecarServer)) {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'SIDECAR_REQUIRED_FIELD_MISSING' -Reason 'pending sidecar manifest is missing local_file or server_out.' -Status 'invalid_manifest' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }
    $localBoundary = Test-PendingManifestPathBoundary -Path $sidecarLocal -Root $pendingRoot -AllowMissingLeaf:$AllowMissingLocal
    if (-not $localBoundary.Ok) {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode "SIDECAR_LOCAL_$($localBoundary.ReasonCode)" -Reason "pending sidecar local_file is not a trusted PendingServerPush payload ($($localBoundary.ReasonCode)): $sidecarLocal" -Status 'invalid_manifest' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }

    $outputRoot = Get-PendingManifestConfiguredOutputRoot -Manifest $Manifest
    $serverBoundary = Test-PendingManifestPathBoundary -Path $sidecarServer -Root $outputRoot -AllowMissingLeaf
    if (-not $serverBoundary.Ok) {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode "SIDECAR_SERVER_$($serverBoundary.ReasonCode)" -Reason "pending sidecar server_out is not inside the configured output root ($($serverBoundary.ReasonCode)): $sidecarServer" -Status 'invalid_manifest' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }
    $forbiddenRoots = @(
        @(Get-PendingManifestConfiguredSourceRoots),
        (Get-PendingScriptVariableText -Name 'LocalBase'),
        $pendingRoot
    )
    $forbidden = Test-PendingManifestPathOutsideForbiddenRoots -Path $sidecarServer -Roots $forbiddenRoots -Label 'pending sidecar server_out' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    if (-not $forbidden.Ok) { return $forbidden }

    return New-PendingManifestTrustResult -Ok:$true -ReasonCode 'OK' -Reason 'ok' -Status 'trusted' -ManifestPath $ManifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
}

function Get-PendingManifestLocalEncodedRoot {
    $localEncoded = Get-PendingScriptVariableText -Name 'LocalEncoded'
    if (-not [string]::IsNullOrWhiteSpace($localEncoded)) { return $localEncoded }
    $localBase = Get-PendingScriptVariableText -Name 'LocalBase'
    if (-not [string]::IsNullOrWhiteSpace($localBase)) { return (Join-Path $localBase 'Encoded') }
    return ''
}

function Test-PendingManifestTrustedForRepair {
    param(
        [Parameter(Mandatory)] [System.IO.FileInfo] $ManifestFile,
        [Parameter(Mandatory)] $Manifest
    )

    $manifestPath = Get-PendingManifestFilePathText -ManifestFile $ManifestFile
    $localFile = Get-PendingManifestText -Object $Manifest -Name 'local_file'
    $serverOut = Get-PendingManifestText -Object $Manifest -Name 'server_out'
    $sourcePath = Get-PendingManifestText -Object $Manifest -Name 'source_path'
    $pendingRoot = Get-PendingScriptVariableText -Name 'LocalPendingPush'
    $localEncodedRoot = Get-PendingManifestLocalEncodedRoot

    $contract = Test-PendingManifestCurrentContractFields -Manifest $Manifest -ManifestPath $manifestPath
    if (-not $contract.Ok) { return $contract }

    $state = Get-PendingManifestText -Object $Manifest -Name 'manifest_state'
    if ($state -ne 'pending_move') {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'REPAIR_STATE_UNSUPPORTED' -Reason "Only pending_move manifests are repairable automatically; got '$state'." -Status 'invalid_manifest' -ManifestPath $manifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }

    $manifestBoundary = Test-PendingManifestPathBoundary -Path $manifestPath -Root $pendingRoot
    if (-not $manifestBoundary.Ok) {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode "MANIFEST_$($manifestBoundary.ReasonCode)" -Reason "Manifest file is not inside LocalPendingPush ($($manifestBoundary.ReasonCode)): $manifestPath" -Status 'invalid_manifest' -ManifestPath $manifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }
    $localBoundary = Test-PendingManifestPathBoundary -Path $localFile -Root $pendingRoot -AllowMissingLeaf
    if (-not $localBoundary.Ok) {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode "LOCAL_$($localBoundary.ReasonCode)" -Reason "local_file is not inside PendingServerPush ($($localBoundary.ReasonCode)): $localFile" -Status 'invalid_manifest' -ManifestPath $manifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }
    $destination = Test-PendingManifestDestinationTrusted -Manifest $Manifest -ManifestPath $manifestPath
    if (-not $destination.Ok) { return $destination }

    $original = Get-PendingManifestText -Object $Manifest -Name 'original_local_file'
    if ([string]::IsNullOrWhiteSpace($original)) {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'ORIGINAL_LOCAL_FILE_MISSING' -Reason 'original_local_file is required for pending_move repair.' -Status 'invalid_manifest' -ManifestPath $manifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }
    $originalBoundary = Test-PendingManifestPathBoundary -Path $original -Root $localEncodedRoot -AllowMissingLeaf
    if (-not $originalBoundary.Ok) {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode "ORIGINAL_$($originalBoundary.ReasonCode)" -Reason "original_local_file is not inside the local encoded output root ($($originalBoundary.ReasonCode)): $original" -Status 'invalid_manifest' -ManifestPath $manifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }
    $forbiddenOriginal = Test-PendingManifestPathOutsideForbiddenRoots -Path $original -Roots @(@(Get-PendingManifestConfiguredSourceRoots), (Get-PendingScriptVariableText -Name 'Outsource'), (Get-PendingScriptVariableText -Name 'LocalPendingPush')) -Label 'original_local_file' -ManifestPath $manifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    if (-not $forbiddenOriginal.Ok) { return $forbiddenOriginal }
    if (-not (Test-Path -LiteralPath $localFile -ErrorAction SilentlyContinue) -and -not (Test-Path -LiteralPath $original -PathType Leaf -ErrorAction SilentlyContinue)) {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'ORIGINAL_PAYLOAD_MISSING' -Reason "pending_move original_local_file is missing: $original" -Status 'missing_payload' -ManifestPath $manifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }

    foreach ($sidecar in @(Get-PendingSidecarEntries -Manifest $Manifest)) {
        $sidecarTrust = Test-PendingSidecarTrustedForPublish -Manifest $Manifest -Sidecar $sidecar -ManifestPath $manifestPath -AllowMissingLocal
        if (-not $sidecarTrust.Ok) { return $sidecarTrust }
        $sidecarLocal = Get-PendingManifestText -Object $sidecar -Name 'local_file'
        $sidecarOriginal = Get-PendingManifestText -Object $sidecar -Name 'original_local_file'
        if ([string]::IsNullOrWhiteSpace($sidecarOriginal)) {
            return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'SIDECAR_ORIGINAL_MISSING' -Reason 'pending sidecar original_local_file is required for pending_move repair.' -Status 'invalid_manifest' -ManifestPath $manifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
        }
        $sidecarOriginalBoundary = Test-PendingManifestPathBoundary -Path $sidecarOriginal -Root $localEncodedRoot -AllowMissingLeaf
        if (-not $sidecarOriginalBoundary.Ok) {
            return New-PendingManifestTrustResult -Ok:$false -ReasonCode "SIDECAR_ORIGINAL_$($sidecarOriginalBoundary.ReasonCode)" -Reason "pending sidecar original_local_file is not inside the local encoded output root ($($sidecarOriginalBoundary.ReasonCode)): $sidecarOriginal" -Status 'invalid_manifest' -ManifestPath $manifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
        }
        if (-not (Test-Path -LiteralPath $sidecarLocal -ErrorAction SilentlyContinue) -and -not (Test-Path -LiteralPath $sidecarOriginal -PathType Leaf -ErrorAction SilentlyContinue)) {
            return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'SIDECAR_ORIGINAL_PAYLOAD_MISSING' -Reason "pending sidecar original_local_file is missing: $sidecarOriginal" -Status 'missing_payload' -ManifestPath $manifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
        }
    }

    return New-PendingManifestTrustResult -Ok:$true -ReasonCode 'OK' -Reason 'ok' -Status 'trusted' -ManifestPath $manifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
}

function Test-PendingManifestTrustedForDrain {
    param(
        [Parameter(Mandatory)] [System.IO.FileInfo] $ManifestFile,
        [Parameter(Mandatory)] $Manifest
    )

    $manifestPath = Get-PendingManifestFilePathText -ManifestFile $ManifestFile
    $localFile = Get-PendingManifestText -Object $Manifest -Name 'local_file'
    $serverOut = Get-PendingManifestText -Object $Manifest -Name 'server_out'
    $sourcePath = Get-PendingManifestText -Object $Manifest -Name 'source_path'
    $pendingRoot = Get-PendingScriptVariableText -Name 'LocalPendingPush'

    $contract = Test-PendingManifestCurrentContractFields -Manifest $Manifest -ManifestPath $manifestPath
    if (-not $contract.Ok) { return $contract }

    $manifestBoundary = Test-PendingManifestPathBoundary -Path $manifestPath -Root $pendingRoot
    if (-not $manifestBoundary.Ok) {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode "MANIFEST_$($manifestBoundary.ReasonCode)" -Reason "Manifest file is not inside LocalPendingPush ($($manifestBoundary.ReasonCode)): $manifestPath" -Status 'invalid_manifest' -ManifestPath $manifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }

    $state = Get-PendingManifestText -Object $Manifest -Name 'manifest_state'
    $drainableStates = @('parked', 'parked_recovered', 'missing_payload', 'retry_copy_failed', 'retry_reveal_failed', 'retry_sidecar_file_failed', 'retry_sidecar_backup_failed', 'retry_sidecar_failed')
    if ($state -notin $drainableStates) {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'DRAIN_STATE_UNSUPPORTED' -Reason "Manifest state '$state' is not drainable automatically." -Status 'invalid_manifest' -ManifestPath $manifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }

    $localBoundary = Test-PendingManifestPathBoundary -Path $localFile -Root $pendingRoot -AllowMissingLeaf
    if (-not $localBoundary.Ok) {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode "LOCAL_$($localBoundary.ReasonCode)" -Reason "local_file is not inside PendingServerPush ($($localBoundary.ReasonCode)): $localFile" -Status 'invalid_manifest' -ManifestPath $manifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }
    if (-not (Test-Path -LiteralPath $localFile -PathType Leaf -ErrorAction SilentlyContinue)) {
        return New-PendingManifestTrustResult -Ok:$false -ReasonCode 'PAYLOAD_MISSING' -Reason "local_file payload is missing; manifest remains queued for operator recovery: $localFile" -Status 'missing_payload' -ManifestPath $manifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
    }

    $destination = Test-PendingManifestDestinationTrusted -Manifest $Manifest -ManifestPath $manifestPath
    if (-not $destination.Ok) { return $destination }

    foreach ($sidecar in @(Get-PendingSidecarEntries -Manifest $Manifest)) {
        $sidecarTrust = Test-PendingSidecarTrustedForPublish -Manifest $Manifest -Sidecar $sidecar -ManifestPath $manifestPath
        if (-not $sidecarTrust.Ok) { return $sidecarTrust }
    }

    return New-PendingManifestTrustResult -Ok:$true -ReasonCode 'OK' -Reason 'ok' -Status 'trusted' -ManifestPath $manifestPath -LocalFile $localFile -ServerOut $serverOut -SourcePath $sourcePath
}

function Update-PendingManifestTx3gFailures {
    param(
        [Parameter(Mandatory)] [string] $ManifestPath,
        [Parameter(Mandatory)] $Manifest,
        [array] $Failures = @()
    )

    $failureList = @($Failures | Where-Object { $null -ne $_ })
    if ($failureList.Count -eq 0) { return }

    try {
        $currentManifest = $Manifest
        if (Test-Path -LiteralPath $ManifestPath -ErrorAction SilentlyContinue) {
            try {
                $currentManifest = Read-PendingManifestFile -Path $ManifestPath
            } catch {}
        }
        $map = ConvertTo-PendingManifestMap $currentManifest
        $map['tx3g_srt_failures'] = @($failureList)
        $map['last_tx3g_sidecar_failure_at'] = (Get-Date -Format 'o')
        $map['last_tx3g_sidecar_failure_reason'] = [string]$failureList[0].Reason
        Write-PendingManifestFile -Path $ManifestPath -Manifest $map | Out-Null
    } catch {
        Write-Log "Pending: failed to persist tx3g sidecar failure details to manifest $ManifestPath : $_" "WARN"
    }
}

function Update-PendingManifestRetryState {
    param(
        [Parameter(Mandatory)] [string] $ManifestPath,
        [Parameter(Mandatory)] $Manifest,
        [Parameter(Mandatory)] [string] $State,
        [string] $Reason = '',
        [string] $Stage = '',
        [array] $Tx3gFailures = @()
    )

    try {
        $map = ConvertTo-PendingManifestMap $Manifest
        $map['manifest_state'] = $State
        $map['last_retry_at'] = (Get-Date -Format 'o')
        if (-not [string]::IsNullOrWhiteSpace($Stage)) {
            $map['last_retry_stage'] = $Stage
        }
        if (-not [string]::IsNullOrWhiteSpace($Reason)) {
            $map['last_retry_error'] = $Reason
        }
        $tx3gFailureList = @($Tx3gFailures | Where-Object { $null -ne $_ })
        if ($tx3gFailureList.Count -gt 0) {
            $map['tx3g_srt_failures'] = @($tx3gFailureList)
            $map['last_tx3g_sidecar_failure_at'] = (Get-Date -Format 'o')
            $map['last_tx3g_sidecar_failure_reason'] = [string]$tx3gFailureList[0].Reason
        }
        $retryCount = 0
        try {
            if ($map.Contains('retry_count') -and $null -ne $map['retry_count']) {
                $retryCount = [int]$map['retry_count']
            }
        } catch {
            $retryCount = 0
        }
        $map['retry_count'] = $retryCount + 1
        Write-PendingManifestFile -Path $ManifestPath -Manifest $map | Out-Null
    } catch {
        Write-Log "Pending: failed to persist retry state '$State' to manifest $ManifestPath : $_" "WARN"
    }
}

function Test-PendingManifestRoundTripValid {
    param([Parameter(Mandatory)] $RoundTrip)

    foreach ($key in @('local_file', 'server_out')) {
        $value = Get-PendingObjectProperty -Object $RoundTrip -Name $key
        if ([string]::IsNullOrWhiteSpace([string]$value)) {
            return [pscustomobject]@{ Ok = $false; Reason = "$key missing" }
        }
    }

    $schemaVersion = [string](Get-PendingObjectProperty -Object $RoundTrip -Name 'schema_version')
    if ([string]::IsNullOrWhiteSpace($schemaVersion)) {
        return [pscustomobject]@{ Ok = $true; Reason = 'legacy manifest' }
    }
    if ($schemaVersion -ne 'pending_push_manifest.v1') {
        return [pscustomobject]@{ Ok = $false; Reason = 'schema_version mismatch' }
    }

    $requiredText = @(
        'pipeline_version',
        'publish_transaction_id',
        'manifest_state',
        'route',
        'local_file',
        'server_out',
        'source_identity_v2',
        'source_identity_v2_algorithm',
        'source_path'
    )
    foreach ($key in $requiredText) {
        $value = Get-PendingObjectProperty -Object $RoundTrip -Name $key
        if ([string]::IsNullOrWhiteSpace([string]$value)) {
            return [pscustomobject]@{ Ok = $false; Reason = "$key missing" }
        }
    }

    $outputSize = Get-PendingObjectProperty -Object $RoundTrip -Name 'output_size'
    if ($null -eq $outputSize) {
        return [pscustomobject]@{ Ok = $false; Reason = 'output_size missing' }
    }
    try {
        if ([long]$outputSize -lt 0) {
            return [pscustomobject]@{ Ok = $false; Reason = 'output_size negative' }
        }
    } catch {
        return [pscustomobject]@{ Ok = $false; Reason = 'output_size invalid' }
    }

    $requiredArrays = @(
        'sidecar_files',
        'tx3g_srt_tracks',
        'tx3g_srt_failures',
        'bdpgs_srt_failures',
        'vobsub_srt_failures',
        'tx3g_embedded_srt_tracks',
        'bdpgs_embedded_srt_tracks',
        'vobsub_embedded_srt_tracks'
    )
    foreach ($key in $requiredArrays) {
        if ($null -eq $RoundTrip.PSObject.Properties[$key]) {
            return [pscustomobject]@{ Ok = $false; Reason = "$key missing" }
        }
    }

    return [pscustomobject]@{ Ok = $true; Reason = 'ok' }
}

# Atomic manifest write with round-trip validation. Same temp-file-then-Replace
# dance as Write-Sidecar but with stricter post-write validation: the manifest
# is only valid if local_file and server_out both round-trip non-empty. Current
# schema manifests also must preserve transaction, identity, output-size, and
# sidecar/subtitle state fields; legacy manifests remain writable so existing
# parked jobs can still be recovered and drained. On any failure the temp/backup
# files are cleaned up and the original exception is re-thrown so callers can
# decide whether to retry.
function Write-PendingManifestFile {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] $Manifest
    )

    $dir = Split-Path $Path -Parent
    if (-not (Test-Path -LiteralPath $dir)) {
        [System.IO.Directory]::CreateDirectory($dir) | Out-Null
    }
    $leaf = Split-Path $Path -Leaf
    $id = [guid]::NewGuid().ToString("N")
    $tmp = Join-Path $dir ".$leaf.$id.tmp"
    $backup = Join-Path $dir ".$leaf.$id.bak"
    try {
        # S1 — Depth 5 truncated route_plan.decision_trace[].data and other
        # nested fields the deferred-publish sidecar then inherits.  Match
        # the sidecar Depth 10 so a parked-then-drained job carries the
        # same metadata as an immediate publish.
        $json = $Manifest | ConvertTo-Json -Depth 10
        [System.IO.File]::WriteAllText($tmp, $json, [System.Text.UTF8Encoding]::new($false))
        $roundTrip = Read-PendingManifestFile -Path $tmp
        $validation = Test-PendingManifestRoundTripValid -RoundTrip $roundTrip
        if (-not $validation.Ok) {
            throw "pending manifest validation failed: $($validation.Reason)"
        }

        if ([System.IO.File]::Exists($Path)) {
            [System.IO.File]::Replace($tmp, $Path, $backup, $true)
            Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        } else {
            [System.IO.File]::Move($tmp, $Path)
        }
        return $true
    } catch {
        if ($tmp -and (Test-Path -LiteralPath $tmp -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
        if ($backup -and (Test-Path -LiteralPath $backup -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        }
        throw
    }
}
