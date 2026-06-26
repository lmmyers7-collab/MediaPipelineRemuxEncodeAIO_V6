# ==============================================================================
# ops\pipeline\engine\library\library_index.ps1
# ==============================================================================
# Outsource processed index, source scan caches, rescan flag consumption, and
# already-processed decisions.
#
# Dot-sourced from MediaPipeline.ps1. Reads/writes at call time:
#   $Outsource, $SourceMovies, $SourceTV, $RescanFlag
#   $script:IndexScanTimeoutSeconds, $script:SourceScanTimeoutSeconds
#   $script:ProcessedIndexCache, $script:MovieScanCache, $script:TVScanCache
#
# Cross-module/main helpers:
#   Write-Log, Invoke-RecursivePathScan
#   Normalize-MovieName, Get-CleanMovieName, Get-SafeLocalName
#   Get-OutputPaths, Test-PendingPublishMatch, Test-OutputNeedsReprocess
# ==============================================================================
function Build-ProcessedIndex {
    # FIX#9: the old version used Wait-Job -Timeout 120 and returned an
    # empty index on timeout, which caused Already-Processed to fall
    # back to "not in index" and skip sidecar version checks entirely -
    # meaning no reprocessing happened for any movie on a large library.
    # We now respect IndexScanTimeoutSeconds (default 1800s) and
    # never claim success with an empty index when the scan actually ran.
    Write-Log "Building processed index from outsource..."
    $idx = @{ Movies=@{}; TVShows=@{} }
    $timeout = $script:IndexScanTimeoutSeconds
    try {
        $outFiles = @(Invoke-RecursivePathScan -Path $Outsource -ItemType File -TimeoutSeconds $timeout -Label "outsource index scan")
        foreach ($fullName in $outFiles) {
            if ([string]::IsNullOrWhiteSpace([string]$fullName)) { continue }
            $fname   = [System.IO.Path]::GetFileName([string]$fullName)
            $fdir    = [System.IO.Path]::GetDirectoryName([string]$fullName)
            $dirName = Split-Path $fdir -Leaf

            if ($fname -match '(.+?) - S(\d{2})E(\d{2})-E(\d{2})') {
                # 4) Multi-episode output: index every episode in the range individually
                $mShow = $Matches[1]; $mSeason = $Matches[2]
                $mStart = [int]$Matches[3]; $mEnd = [int]$Matches[4]
                for ($mEp = $mStart; $mEp -le $mEnd; $mEp++) {
                    $idx.TVShows["${mShow}_S${mSeason}E$($mEp.ToString('00'))"] = $true
                }
            } elseif ($fname -match '(.+?) - S(\d{2})E(\d{2})') {
                $idx.TVShows["$($Matches[1])_S$($Matches[2])E$($Matches[3])"] = $true
            } elseif ($dirName -match '^Season \d{2}$') {
                if ($fname -match 'S(\d{2})E(\d{2})') {
                    $show = Split-Path (Split-Path $fdir -Parent) -Leaf
                    $idx.TVShows["${show}_S$($Matches[1])E$($Matches[2])"] = $true
                }
            } else {
                # FIX#8: also key on the PARENT FOLDER name, not just the
                # file's leaf. Movies are laid out as
                #   <Outsource>\<Movie (Year)>\<Movie (Year)>.mkv
                # The folder name IS the Get-CleanMovieName output, so
                # indexing it directly guarantees the key matches what
                # Already-Processed computes from the source file.
                $idx.Movies[(Normalize-MovieName $fname)] = $true
                if ($dirName) {
                    $idx.Movies[$dirName.ToLowerInvariant()] = $true
                }
            }
        }
        Write-Log "Indexed $($idx.Movies.Count) movies / $($idx.TVShows.Count) TV episodes"
    } catch { Write-Log "Outsource scan failed - using empty index: $_" "WARN" }
    return $idx
}

function Already-Processed {
    param($file, [bool]$isTV, $tvInfo, $idx)

    # Compute expected output path so we can inspect the sidecar.
    # Process-File has already computed safeName; recompute here locally -
    # the cost is negligible and keeps the function self-contained.
    $safeName = Get-SafeLocalName $file.Name
    $paths    = Get-OutputPaths $file $isTV $tvInfo $safeName

    if (Test-PendingPublishMatch -SourceFile $file -ServerOut $paths.ServerOut) {
        if ($isTV) {
            Write-Log "SKIP (pending publish queued): $($tvInfo.ShowName) S$($tvInfo.Season.ToString('00'))E$($tvInfo.Episode.ToString('00'))"
        } else {
            Write-Log "SKIP (pending publish queued): $($file.Name)"
        }
        return $true
    }

    $inIndex = $false
    if ($isTV) {
        $tvPlan = if ($paths.ContainsKey('PlexPlan')) { $paths.PlexPlan } else { $null }
        $key = if ($tvPlan -and $tvPlan.IdentityKey) {
            [string]$tvPlan.IdentityKey
        } else {
            "$($tvInfo.ShowName)_S$($tvInfo.Season.ToString('00'))E$($tvInfo.Episode.ToString('00'))"
        }
        $inIndex = $idx.TVShows.ContainsKey($key)
    } else {
        # FIX#8: check BOTH the normalized source name and the clean output
        # folder name (lowercased). With Normalize-MovieName now delegating
        # to Get-CleanMovieName, these should agree for new outputs, but
        # we keep both paths for backward compatibility with indices built
        # before this fix.
        $n     = Normalize-MovieName $file.Name
        $clean = (Get-CleanMovieName $file.Name).ToLowerInvariant()
        $inIndex = $idx.Movies.ContainsKey($n) -or $idx.Movies.ContainsKey($clean)
    }

    # FIX#8/9: even when the index says "not present", perform a direct
    # Test-Path on the expected output path. This covers two failure
    # modes: (a) the index scan timed out or returned partial results,
    # and (b) the show name parsed from the source differs slightly from
    # the folder name on the outsource. Without this fallback, any
    # indexing hiccup caused the pipeline to unnecessarily re-encode
    # already-processed content.
    if (-not $inIndex -and (Test-Path -LiteralPath $paths.ServerOut)) {
        Write-Log "Already-Processed: fallback Test-Path hit for $(Split-Path $paths.ServerOut -Leaf)" "DEBUG"
        $inIndex = $true
    }

    if (-not $inIndex) { return $false }

    # File is on the outsource. Should we reprocess it?
    # Yes when: ReprocessAll=true, no sidecar, or sidecar version < min.
    if (Test-OutputNeedsReprocess -OutputPath $paths.ServerOut -SourceFile $file) {
        $reason = if ($script:ReprocessAll) { "ReprocessAll" } else { "stale pipeline version" }
        Write-Log "REPROCESS ($reason): $(Split-Path $paths.ServerOut -Leaf) - keeping current output until replacement is verified"
        return $false
    }

    if ($isTV) {
        Write-Log "SKIP (already in outsource): $($tvInfo.ShowName) S$($tvInfo.Season.ToString('00'))E$($tvInfo.Episode.ToString('00'))"
    } else {
        Write-Log "SKIP (already in outsource): $($file.Name)"
    }
    return $true
}

function Get-CacheAgeSeconds {
    param($Timestamp)
    if (-not $Timestamp) { return [double]::PositiveInfinity }
    return ((Get-Date) - $Timestamp).TotalSeconds
}

function Consume-RescanFlag {
    $rescanInfo = Get-ControlFlagInfo -Path $RescanFlag
    if (-not $rescanInfo.Exists) { return $false }
    Register-ControlFlagObservation -Kind rescan -Info $rescanInfo
    try {
        Remove-Item -LiteralPath $RescanFlag -Force -ErrorAction SilentlyContinue
    } catch {}
    Write-Log "Manual rescan requested via $RescanFlag" "WARN"
    return $true
}

function Invalidate-ProcessedIndexCache {
    $script:ProcessedIndexCache = $null
    $script:ProcessedIndexCacheAt = $null
    $script:ForceProcessedIndexRefresh = $true
}

function Get-ChildItemWithRetry {
    param([string]$Path, [int]$MaxRetries = 2)
    for ($i = 0; $i -lt $MaxRetries; $i++) {
        try {
            $paths = @(Invoke-RecursivePathScan -Path $Path -ItemType File -TimeoutSeconds $script:SourceScanTimeoutSeconds -Label "source scan")
            return @(
                $paths | ForEach-Object {
                    try { Get-Item -LiteralPath ([string]$_) -ErrorAction Stop } catch { $null }
                } | Where-Object { $null -ne $_ }
            )
        }
        catch {
            if ($i -eq $MaxRetries - 1) {
                Write-Log "Failed to scan $Path after $MaxRetries attempts: $_" "ERROR"; return @()
            }
            Write-Log "Scan of $Path failed, retry $($i+1)/$MaxRetries ($_)" "WARN"
            if (-not (Start-StopAwareSleep 10)) { return @() }
        }
    }
    return @()
}

function Get-CachedSourceFiles {
    param(
        [ValidateSet('movies', 'tv')] [string] $Kind,
        [string] $Path,
        [bool] $ForceRefresh = $false
    )

    $ttl = [int]$script:SourceScanIntervalSeconds
    $cacheProp = if ($Kind -eq 'movies') { 'MovieScanCache' } else { 'TVScanCache' }
    $stampProp = if ($Kind -eq 'movies') { 'MovieScanCacheAt' } else { 'TVScanCacheAt' }
    $cached = Get-Variable -Scope Script -Name $cacheProp -ValueOnly
    $stamp  = Get-Variable -Scope Script -Name $stampProp -ValueOnly
    $age    = Get-CacheAgeSeconds $stamp

    $shouldRefresh = $ForceRefresh -or -not $stamp -or $ttl -le 0 -or $age -ge $ttl
    if ($shouldRefresh) {
        $files = @(Get-ChildItemWithRetry $Path)
        $scanStatus = [string]$script:LastRecursivePathScanStatus
        if ($scanStatus -in @('timeout', 'stopped', 'error') -and $stamp -and @($cached).Count -gt 0) {
            Write-Log ("Source scan {0} for {1}; preserving last-good {2} cache with {3} file(s)" -f $scanStatus, $Kind, $Kind, @($cached).Count) "WARN"
            return @($cached)
        }
        Set-Variable -Scope Script -Name $cacheProp -Value $files
        Set-Variable -Scope Script -Name $stampProp -Value (Get-Date)
        Write-Log ("Source scan refreshed ({0}): {1} file(s)" -f $Kind, $files.Count) "DEBUG"
        return $files
    }

    Write-Log ("Using cached {0} scan ({1:N0}s old, {2} file(s))" -f $Kind, $age, @($cached).Count) "DEBUG"
    return @($cached)
}

function Get-MediaQueueDiscoveryPlan {
    param(
        [string] $MovieRoot = $SourceMovies,
        [string] $TVRoot = $SourceTV,
        [bool] $ForceRefresh = $false
    )

    $profiles = if (Get-Command -Name Get-MediaPipelineLibraryProfiles -ErrorAction SilentlyContinue) {
        @(Get-MediaPipelineLibraryProfiles)
    } else {
        @()
    }

    if (@($profiles).Count -gt 0) {
        $movieList = [System.Collections.Generic.List[object]]::new()
        $tvList = [System.Collections.Generic.List[object]]::new()
        foreach ($profile in $profiles) {
            $enabled = Get-MediaPipelineProfileProperty -Profile $profile -Name 'enabled' -Default $true
            if ($enabled -is [string]) {
                $enabled = $enabled.Trim().ToLowerInvariant() -notin @('false','0','no','off','disabled')
            }
            if (-not [bool]$enabled) { continue }
            $sourceRoot = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'source_path' -Default '')
            if ([string]::IsNullOrWhiteSpace($sourceRoot)) { continue }
            $designation = ([string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'designation' -Default 'auto')).Trim().ToLowerInvariant()
            if ($designation -in @('mixed','custom','')) { $designation = 'auto' }
            if ($designation -notin @('movie','tv','auto')) { $designation = 'auto' }
            $isTvProfile = $designation -eq 'tv'
            $isAutoProfile = $designation -eq 'auto'
            $kind = if ($isTvProfile) { 'tv' } else { 'movies' }
            $files = @()
            if (-not $isAutoProfile -and (($isTvProfile -and $sourceRoot -eq $TVRoot) -or (-not $isTvProfile -and $sourceRoot -eq $MovieRoot))) {
                $files = @(Get-CachedSourceFiles -Kind $kind -Path $sourceRoot -ForceRefresh:$ForceRefresh)
            } else {
                $files = @(Get-ChildItemWithRetry $sourceRoot)
                Write-Log ("Source scan refreshed (library profile {0}): {1} file(s)" -f ([string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'id' -Default '')), $files.Count) "DEBUG"
            }
            $settingsOverrides = if (Get-Command -Name Get-MediaPipelineLibraryProfileOverrideMap -ErrorAction SilentlyContinue) {
                Get-MediaPipelineLibraryProfileOverrideMap -Profile $profile
            } else {
                [ordered]@{}
            }
            $effectiveSettings = if (Get-Command -Name Resolve-MediaPipelineLibraryEffectiveSettings -ErrorAction SilentlyContinue) {
                Resolve-MediaPipelineLibraryEffectiveSettings -Profile $profile -Overrides $settingsOverrides
            } else {
                [ordered]@{}
            }
            $libraryMetadata = @{
                library_id = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'id' -Default '')
                library_name = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'name' -Default '')
                designation = $designation
                source_root = $sourceRoot
                output_root = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'output_path' -Default $Outsource)
                settings_override_keys = @($settingsOverrides.Keys)
                settings_overrides = $settingsOverrides
                effective_settings = $effectiveSettings
            }
            if ($isAutoProfile) {
                $movieFiles = [System.Collections.Generic.List[object]]::new()
                $tvFiles = [System.Collections.Generic.List[object]]::new()
                foreach ($file in @($files)) {
                    if ($null -eq $file) { continue }
                    $kindInfo = $null
                    if (Get-Command -Name Resolve-SingleFileMediaKind -ErrorAction SilentlyContinue) {
                        $kindInfo = Resolve-SingleFileMediaKind -Path ([string]$file.FullName) -SourceMovies $MovieRoot -SourceTV $TVRoot
                    }
                    $isTvFile = if ($kindInfo) {
                        [bool]$kindInfo.IsTV
                    } else {
                        ([string]$file.FullName) -match '(?i)[/\\]Season\s+\d+[/\\]' -or
                        ([string]$file.Name) -match '(?i)(?<!\d)S\d{1,2}E\d{1,3}(?!\d)'
                    }
                    if ($isTvFile) {
                        [void]$tvFiles.Add($file)
                    } else {
                        [void]$movieFiles.Add($file)
                    }
                }
                $priorityManifest = Get-PriorityManifest
                $movieEntries = @(
                    Get-QueuedEntries `
                        @($movieFiles.ToArray()) `
                        -RootPath $sourceRoot `
                        -IsTV:$false `
                        -LibraryProfileMetadata $libraryMetadata `
                        -PriorityManifest $priorityManifest
                )
                $tvEntries = @(
                    Get-QueuedEntries `
                        @($tvFiles.ToArray()) `
                        -RootPath $sourceRoot `
                        -IsTV:$true `
                        -LibraryProfileMetadata $libraryMetadata `
                        -PriorityManifest $priorityManifest
                )
                foreach ($entry in $movieEntries) { [void]$movieList.Add($entry) }
                foreach ($entry in $tvEntries) { [void]$tvList.Add($entry) }
                continue
            }
            $entries = @(
                Get-QueuedEntries `
                    $files `
                    -RootPath $sourceRoot `
                    -IsTV:$isTvProfile `
                    -LibraryProfileMetadata $libraryMetadata
            )
            if ($isTvProfile) {
                foreach ($entry in $entries) { [void]$tvList.Add($entry) }
            } else {
                foreach ($entry in $entries) { [void]$movieList.Add($entry) }
            }
        }
        return New-MediaQueuePhasePlan -MovieEntries @($movieList.ToArray()) -TVEntries @($tvList.ToArray())
    }

    $movieEntries = @(
        Get-QueuedEntries `
            (Get-CachedSourceFiles -Kind 'movies' -Path $MovieRoot -ForceRefresh:$ForceRefresh) `
            -RootPath $MovieRoot
    )
    $tvEntries = @(
        Get-QueuedEntries `
            (Get-CachedSourceFiles -Kind 'tv' -Path $TVRoot -ForceRefresh:$ForceRefresh) `
            -RootPath $TVRoot `
            -IsTV
    )

    return New-MediaQueuePhasePlan -MovieEntries $movieEntries -TVEntries $tvEntries
}

function Get-ProcessedIndexCached {
    param([bool]$ForceRefresh = $false)

    $ttl = [int]$script:ProcessedIndexRefreshSeconds
    $age = Get-CacheAgeSeconds $script:ProcessedIndexCacheAt
    $shouldRefresh = $ForceRefresh -or
        $script:ForceProcessedIndexRefresh -or
        -not $script:ProcessedIndexCacheAt -or
        $ttl -le 0 -or
        $age -ge $ttl

    if ($shouldRefresh) {
        $script:ProcessedIndexCache = Build-ProcessedIndex
        $script:ProcessedIndexCacheAt = Get-Date
        $script:ForceProcessedIndexRefresh = $false
        return $script:ProcessedIndexCache
    }

    Write-Log ("Using cached processed index ({0:N0}s old)" -f $age) "DEBUG"
    return $script:ProcessedIndexCache
}
