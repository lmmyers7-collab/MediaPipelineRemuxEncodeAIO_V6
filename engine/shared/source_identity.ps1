# ==============================================================================
# engine\shared\source_identity.ps1
# ==============================================================================
# Safe local names and source identity keys used by reprocess checks, failure
# markers, sidecars, and pending-push manifests.
#
# Dot-sourced by the engine entrypoints and legacy compatibility loaders. Reads at call time:
#   $script:SourceIdentityV2Algorithm
#
# Cross-module/main helpers:
#   Remove-PriorityMarkersFromName
#   Get-MediaDuration, Get-SourceVideoCodec
#   Write-Log
# ==============================================================================
function Get-SafeLocalName {
    param([string]$FileName)
    $base = Remove-PriorityMarkersFromName ([System.IO.Path]::GetFileNameWithoutExtension($FileName))
    $ext  = [System.IO.Path]::GetExtension($FileName)
    $safe = $base -replace '\[','' -replace '\]','' -replace '[<>:"/\\|?*]','_' -replace '\s+',' '
    return ($safe.Trim() + $ext)
}

function Get-SourceIdentityKey {
    param($SourceFile)
    if ($null -eq $SourceFile) { return $null }

    $fingerprint = "{0}|{1}|{2}" -f [string]$SourceFile.FullName, [long]$SourceFile.Length, $SourceFile.LastWriteTimeUtc.ToString('o')

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($fingerprint)
        $hash  = $sha.ComputeHash($bytes)
        return -join ($hash | ForEach-Object { $_.ToString('x2') })
    } finally {
        if ($sha) { $sha.Dispose() }
    }
}

function Get-SourceSampleHash {
    param(
        [string] $Path,
        [int] $SampleBytes = 1048576
    )

    $stream = $null
    $sha = $null
    try {
        if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -ErrorAction SilentlyContinue)) {
            return ""
        }
        $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        $sha = [System.Security.Cryptography.SHA256]::Create()
        $sampleByteCount = [int][math]::Max(1, $SampleBytes)
        $buffer = [byte[]]::new($sampleByteCount)

        $read = $stream.Read($buffer, 0, [int][math]::Min([int64]$buffer.Length, [math]::Min([int64]$stream.Length, [int64]$SampleBytes)))
        if ($read -gt 0) {
            [void]$sha.TransformBlock($buffer, 0, $read, $buffer, 0)
        }

        if ($stream.Length -gt $SampleBytes) {
            [void]$stream.Seek([math]::Max([int64]0, [int64]$stream.Length - [int64]$SampleBytes), [System.IO.SeekOrigin]::Begin)
            $read = $stream.Read($buffer, 0, [int][math]::Min([int64]$buffer.Length, [int64]$SampleBytes))
            if ($read -gt 0) {
                [void]$sha.TransformBlock($buffer, 0, $read, $buffer, 0)
            }
        }

        [void]$sha.TransformFinalBlock([byte[]]::new(0), 0, 0)
        return -join ($sha.Hash | ForEach-Object { $_.ToString('x2') })
    } catch {
        Write-Log "Source sample hash failed for $Path : $_" "DEBUG"
        return ""
    } finally {
        if ($stream) { $stream.Dispose() }
        if ($sha) { $sha.Dispose() }
    }
}

function Get-SourceIdentityKeyV2 {
    param($SourceFile)
    if ($null -eq $SourceFile) { return $null }

    $duration = 0.0
    $codec = ''
    $sampleHash = ''
    try { $duration = [math]::Round((Get-MediaDuration $SourceFile.FullName), 3) } catch {}
    try { $codec = [string](Get-SourceVideoCodec $SourceFile.FullName) } catch {}
    try { $sampleHash = [string](Get-SourceSampleHash $SourceFile.FullName) } catch {}

    $fingerprint = "{0}|duration={1}|vcodec={2}|sample={3}" -f `
        [long]$SourceFile.Length,
        $duration.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        $codec.ToLowerInvariant(),
        $sampleHash

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($fingerprint)
        $hash  = $sha.ComputeHash($bytes)
        return -join ($hash | ForEach-Object { $_.ToString('x2') })
    } finally {
        if ($sha) { $sha.Dispose() }
    }
}

function Test-LegacySourceIdentityV2Algorithm {
    param([string]$Algorithm)
    $normalized = ([string]$Algorithm).Trim().ToLowerInvariant()
    return @(
        'legacy',
        'legacy-path-metadata',
        'legacy-path-size-mtime',
        'path-size-mtime',
        'path-size-mtime-v1'
    ) -contains $normalized
}
