# Audit ffprobe and probe-cache helpers.

function Get-Sha256Hex {
    param([string]$Text)

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes([string]$Text)
        $hash = $sha.ComputeHash($bytes)
        return -join ($hash | ForEach-Object { $_.ToString('x2') })
    } finally {
        if ($sha) { $sha.Dispose() }
    }
}

function Get-ProbeCacheSampleHash {
    param(
        $FileInfo,
        [int] $SampleBytes = 1048576
    )

    if ($null -eq $FileInfo -or [string]::IsNullOrWhiteSpace([string]$FileInfo.FullName)) { return '' }
    $stream = $null
    $sha = $null
    try {
        $stream = [System.IO.File]::Open([string]$FileInfo.FullName, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
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
        if (Get-Command -Name Write-AuditLog -ErrorAction SilentlyContinue) {
            Write-AuditLog "Probe cache sample hash failed for $($FileInfo.FullName): $($_.Exception.Message)" 'DEBUG'
        }
        return ''
    } finally {
        if ($stream) { $stream.Dispose() }
        if ($sha) { $sha.Dispose() }
    }
}

function Get-ProbeCacheIdentity {
    param($FileInfo)

    if ($null -eq $FileInfo) { return $null }
    $sampleHash = Get-ProbeCacheSampleHash -FileInfo $FileInfo
    if ([string]::IsNullOrWhiteSpace($sampleHash)) { return $null }
    return "{0}|{1}|{2}|sample_sha256={3}" -f `
        (Convert-ToLowerInvariantSafe ([string]$FileInfo.FullName)), `
        ([int64]$FileInfo.Length), `
        ($FileInfo.LastWriteTimeUtc.ToString('o')), `
        $sampleHash
}

function Get-ProbeCachePath {
    param($FileInfo)

    if (-not $script:ProbeCacheRoot -or $null -eq $FileInfo) { return $null }

    $identity = Get-ProbeCacheIdentity $FileInfo
    if ([string]::IsNullOrWhiteSpace($identity)) { return $null }

    $hash = Get-Sha256Hex $identity
    $bucket = Join-Path $script:ProbeCacheRoot $hash.Substring(0, 2)
    if (-not (Test-Path -LiteralPath $bucket)) {
        New-Item -ItemType Directory -Path $bucket -Force | Out-Null
    }
    return (Join-Path $bucket ($hash + '.json'))
}

function Clear-ProbeCache {
    if (-not $script:ProbeCacheRoot -or -not (Test-Path -LiteralPath $script:ProbeCacheRoot)) { return }

    Get-ChildItem -LiteralPath $script:ProbeCacheRoot -Force -ErrorAction SilentlyContinue |
        Remove-Item -Force -Recurse -ErrorAction SilentlyContinue
}

function Get-ProbeCacheEntry {
    param($FileInfo)

    if ($script:AuditRebuildProbeCache) {
        $script:ProbeCacheMissCount++
        return $null
    }

    $cachePath = Get-ProbeCachePath $FileInfo
    if (-not $cachePath -or -not (Test-Path -LiteralPath $cachePath)) {
        $script:ProbeCacheMissCount++
        return $null
    }

    try {
        $cache = Get-Content -LiteralPath $cachePath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    } catch {
        $script:ProbeCacheMissCount++
        Remove-Item -LiteralPath $cachePath -Force -ErrorAction SilentlyContinue
        return $null
    }

    $expectedIdentity = Get-ProbeCacheIdentity $FileInfo
    if (([string]$cache.cache_schema_version) -ne $script:ProbeCacheSchemaVersion -or
        ([string]$cache.ffprobe_field_set_version) -ne $script:ProbeCacheFieldSetVersion -or
        ([string]$cache.source_identity) -ne $expectedIdentity) {
        $script:ProbeCacheMissCount++
        return $null
    }

    if ($null -eq $cache.data) {
        $script:ProbeCacheMissCount++
        return $null
    }

    $script:ProbeCacheHitCount++
    return @{
        Success  = $true
        Error    = ''
        Data     = $cache.data
        CacheHit = $true
    }
}

function Save-ProbeCacheEntry {
    param(
        $FileInfo,
        $ProbeData
    )

    if ($null -eq $FileInfo -or $null -eq $ProbeData) { return }

    $cachePath = Get-ProbeCachePath $FileInfo
    if (-not $cachePath) { return }

    $payload = [pscustomobject]@{
        cache_schema_version   = $script:ProbeCacheSchemaVersion
        ffprobe_field_set_version = $script:ProbeCacheFieldSetVersion
        cached_at              = (Get-Date -Format 'o')
        source_path            = $FileInfo.FullName
        source_identity        = Get-ProbeCacheIdentity $FileInfo
        data                   = $ProbeData
    }

    Write-AtomicJsonFile -Path $cachePath -InputObject $payload -Depth 16
    $script:ProbeCacheWriteCount++
}

function Invoke-FfprobeJson {
    param([string]$FilePath)

    $probeResult = Invoke-AuditNativeCommand -FilePath $script:FfprobePath -ArgumentList @(
        '-v', 'error',
        '-show_entries', 'format=format_name,duration:stream=index,codec_type,codec_name,codec_long_name,codec_tag_string,codec_tag,channels:stream_tags=language,title:stream_disposition=default,forced',
        '-of', 'json',
        '--', $FilePath
    ) -TimeoutSeconds $FfprobeTimeoutSeconds

    if ($probeResult.ExitCode -ne 0) {
        $message = if ($probeResult.TimedOut) {
            "ffprobe timed out after ${FfprobeTimeoutSeconds}s"
        } elseif ($probeResult.Error) {
            [string]$probeResult.Error
        } else {
            "ffprobe exited with code $($probeResult.ExitCode)"
        }
        return @{
            Success = $false
            Error   = $message
            Data    = $null
        }
    }

    try {
        return @{
            Success = $true
            Error   = ''
            Data    = ($probeResult.Output | ConvertFrom-Json -ErrorAction Stop)
        }
    } catch {
        return @{
            Success = $false
            Error   = "ffprobe returned invalid JSON: $($_.Exception.Message)"
            Data    = $null
        }
    }
}

function Invoke-FfprobeJsonCached {
    param($FileInfo)

    $cached = Get-ProbeCacheEntry -FileInfo $FileInfo
    if ($cached) {
        return $cached
    }

    $probe = Invoke-FfprobeJson -FilePath $FileInfo.FullName
    if ($probe.Success -and $probe.Data) {
        Save-ProbeCacheEntry -FileInfo $FileInfo -ProbeData $probe.Data
    }
    return $probe
}

