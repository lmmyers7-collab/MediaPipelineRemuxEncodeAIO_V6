# Extracted from ops/pipeline/entrypoints/Invoke-RerunCsv.ps1. Responsibility: sidecar, path, review, and manifest evidence

function Get-RerunObjectValue {
    param($Object, [string]$Name, $Default = $null)
    if ($null -eq $Object) { return $Default }
    if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($Name)) { return $Object[$Name] }
    $prop = $Object.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $Default
}

function Set-RerunObjectValue {
    param($Object, [string]$Name, $Value)
    if ($null -eq $Object) { return }
    if ($Object -is [System.Collections.IDictionary]) {
        $Object[$Name] = $Value
        return
    }
    $prop = $Object.PSObject.Properties[$Name]
    if ($prop) {
        $prop.Value = $Value
        return
    }
    $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value -Force
}

function Get-RerunObjectText {
    param($Object, [string]$Name, [string]$Default = '')
    $value = Get-RerunObjectValue -Object $Object -Name $Name -Default $Default
    if ($null -eq $value) { return $Default }
    return [string]$value
}

function Get-RerunArrayField {
    param($Object, [string]$Name)
    $value = Get-RerunObjectValue -Object $Object -Name $Name -Default @()
    if ($null -eq $value) { return @() }
    if ($value -is [array]) { return @($value) }
    if ($value -is [System.Collections.IEnumerable] -and -not ($value -is [string])) { return @($value) }
    return @($value)
}

function Get-RerunBoolField {
    param($Object, [string]$Name)
    $value = Get-RerunObjectValue -Object $Object -Name $Name -Default $false
    if ($value -is [bool]) { return [bool]$value }
    return ([string]$value).Trim().ToLowerInvariant() -eq 'true'
}

function Get-RerunPipelineSidecarPath {
    param([Parameter(Mandatory)] [string]$OutputPath)
    $dir = Split-Path -Parent $OutputPath
    $base = [System.IO.Path]::GetFileNameWithoutExtension($OutputPath)
    return (Join-Path $dir ($base + '.pipeline.json'))
}

function Read-RerunPipelineSidecar {
    param([Parameter(Mandatory)] [string]$OutputPath)
    $sidecar = Get-RerunPipelineSidecarPath -OutputPath $OutputPath
    if (-not (Test-Path -LiteralPath $sidecar -PathType Leaf)) { return $null }
    try {
        return (Get-Content -LiteralPath $sidecar -Raw | ConvertFrom-Json -ErrorAction Stop)
    } catch {
        Write-RerunLog "CSV rerun could not read pipeline sidecar evidence $sidecar : $($_.Exception.Message)" "WARN"
        return $null
    }
}

function Get-RerunTrackSourcePath {
    param($Record)
    foreach ($key in @('local_file','path','Path','srt_path','SrtPath','LocalPath')) {
        $value = Get-RerunObjectText -Object $Record -Name $key -Default ''
        if (-not [string]::IsNullOrWhiteSpace($value)) { return $value }
    }
    return ''
}

function Test-RerunPathUnderRoot {
    param([string]$Path, [string]$Root)
    if ([string]::IsNullOrWhiteSpace($Path) -or [string]::IsNullOrWhiteSpace($Root)) { return $false }
    try {
        $fullPath = [System.IO.Path]::GetFullPath($Path)
        $fullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))
        return ($fullPath.Equals($fullRoot, [System.StringComparison]::OrdinalIgnoreCase) -or $fullPath.StartsWith($fullRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase) -or $fullPath.StartsWith($fullRoot + [System.IO.Path]::AltDirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase))
    } catch {
        return $false
    }
}

function Test-RerunSamePath {
    param([string]$Left, [string]$Right)
    if ([string]::IsNullOrWhiteSpace($Left) -or [string]::IsNullOrWhiteSpace($Right)) { return $false }
    try {
        $leftFull = [System.IO.Path]::GetFullPath($Left).TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))
        $rightFull = [System.IO.Path]::GetFullPath($Right).TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))
        return $leftFull.Equals($rightFull, [System.StringComparison]::OrdinalIgnoreCase)
    } catch {
        return $Left.Trim().TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)).Equals($Right.Trim().TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)), [System.StringComparison]::OrdinalIgnoreCase)
    }
}

function Get-RerunEffectiveFinalOutputRoot {
    param(
        [hashtable]$Config,
        [string]$SourcePath,
        [string]$FallbackRoot
    )

    if ($Config.ContainsKey('LibraryProfiles')) {
        foreach ($profile in @($Config['LibraryProfiles'])) {
            if ($null -eq $profile) { continue }
            $enabled = ConvertTo-RerunBool (Get-RerunProfileField -Profile $profile -Name 'enabled' -Default 'true') $true
            if (-not $enabled) { continue }
            $profileSource = Resolve-RerunPath (Get-RerunProfileField -Profile $profile -Name 'source_path' -Default '')
            if ([string]::IsNullOrWhiteSpace($profileSource)) { continue }
            if (-not (Test-RerunPathUnderRoot -Path $SourcePath -Root $profileSource)) { continue }
            $profileOutput = Resolve-RerunPath (Get-RerunProfileField -Profile $profile -Name 'output_path' -Default '')
            if (-not [string]::IsNullOrWhiteSpace($profileOutput)) { return $profileOutput }
            return $FallbackRoot
        }
    }
    return $FallbackRoot
}

function Get-RerunLibraryProfileEvidenceForPath {
    param(
        [hashtable]$Config,
        [string]$SourcePath,
        [string]$MediaKind = ''
    )

    $fallback = [ordered]@{
        library_id = ''
        library_name = ''
        designation = ''
        source_root = ''
    }
    $tvFallbackSource = ''
    if ($Config.ContainsKey('SourceTV')) {
        $tvFallbackSource = Resolve-RerunPath ([string]$Config['SourceTV'])
    }
    if ($Config.ContainsKey('LibraryProfiles')) {
        $enabledProfiles = @($Config['LibraryProfiles'] | Where-Object {
            $null -ne $_ -and (ConvertTo-RerunBool (Get-RerunProfileField -Profile $_ -Name 'enabled' -Default 'true') $true)
        })
        $matches = @()
        foreach ($profile in $enabledProfiles) {
            $profileSource = Resolve-RerunPath (Get-RerunProfileField -Profile $profile -Name 'source_path' -Default '')
            if ([string]::IsNullOrWhiteSpace($profileSource)) { continue }
            if (Test-RerunPathUnderRoot -Path $SourcePath -Root $profileSource) {
                $matches += [pscustomobject]@{
                    Profile = $profile
                    SourceRoot = $profileSource
                }
            }
        }
        if (@($matches).Count -gt 0) {
            $selected = @($matches | Sort-Object @{ Expression = { ([string]$_.SourceRoot).Length }; Descending = $true } | Select-Object -First 1)[0]
            $profile = $selected.Profile
            return [ordered]@{
                library_id = Get-RerunProfileField -Profile $profile -Name 'id' -Default ''
                library_name = Get-RerunProfileField -Profile $profile -Name 'name' -Default ''
                designation = Get-RerunProfileField -Profile $profile -Name 'designation' -Default ''
                source_root = [string]$selected.SourceRoot
            }
        }

        $tvProfiles = @($enabledProfiles | Where-Object {
            $designation = (Get-RerunProfileField -Profile $_ -Name 'designation' -Default '').Trim().ToLowerInvariant()
            $id = (Get-RerunProfileField -Profile $_ -Name 'id' -Default '').Trim().ToLowerInvariant()
            $designation -eq 'tv' -or $id -eq 'tv'
        })
        if (([string]$MediaKind) -eq 'TV' -and @($tvProfiles).Count -eq 1) {
            $profile = $tvProfiles[0]
            return [ordered]@{
                library_id = Get-RerunProfileField -Profile $profile -Name 'id' -Default ''
                library_name = Get-RerunProfileField -Profile $profile -Name 'name' -Default ''
                designation = Get-RerunProfileField -Profile $profile -Name 'designation' -Default 'tv'
                source_root = Resolve-RerunPath (Get-RerunProfileField -Profile $profile -Name 'source_path' -Default $tvFallbackSource)
            }
        }
    }

    if (([string]$MediaKind) -eq 'TV') {
        $fallback['library_id'] = 'tv'
        $fallback['library_name'] = 'TV'
        $fallback['designation'] = 'tv'
        $fallback['source_root'] = $tvFallbackSource
    }
    return $fallback
}

function Get-RerunFinalOutputRootViolation {
    param(
        [string]$FinalOutputPath,
        [string]$SourcePath,
        [string]$EffectiveRoot,
        [string]$SourceField,
        [bool]$SourceOverwriteConfirmed
    )

    if ([string]::IsNullOrWhiteSpace($FinalOutputPath)) { return 'final output path is unavailable' }
    if ($SourceOverwriteConfirmed -and (Test-RerunSamePath -Left $FinalOutputPath -Right $SourcePath)) { return '' }
    if ([string]::IsNullOrWhiteSpace($EffectiveRoot)) { return 'configured output root is unavailable for final output destination validation' }
    if (Test-RerunPathUnderRoot -Path $FinalOutputPath -Root $EffectiveRoot) { return '' }
    $fieldDetail = if ([string]::IsNullOrWhiteSpace($SourceField)) { '' } else { " from $SourceField" }
    return "final output destination$fieldDetail resolves outside configured output root: $FinalOutputPath"
}

function Get-RerunNormalizedPathKey {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    try {
        return ([System.IO.Path]::GetFullPath($Path).TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))).ToLowerInvariant()
    } catch {
        return ($Path.Trim().TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))).ToLowerInvariant()
    }
}

function Add-RerunAutoReviewIssue {
    param(
        [Parameter(Mandatory)] $Issues,
        [Parameter(Mandatory)] [string]$Code,
        [Parameter(Mandatory)] [string]$Message,
        [string]$Evidence = ''
    )
    $Issues.Add([pscustomobject][ordered]@{
        code = $Code
        message = $Message
        evidence = $Evidence
    }) | Out-Null
}

function Test-RerunObjectHasProperty {
    param($Object, [string]$Name)
    if ($null -eq $Object) { return $false }
    if ($Object -is [System.Collections.IDictionary]) { return $Object.Contains($Name) }
    return ($null -ne $Object.PSObject.Properties[$Name])
}

function Get-RerunAutoReviewIssues {
    param(
        $Plan,
        [Parameter(Mandatory)] [string]$VerifiedOutput
    )
    $issues = [System.Collections.Generic.List[object]]::new()
    $sidecarPath = Get-RerunPipelineSidecarPath -OutputPath $VerifiedOutput
    if (-not (Test-Path -LiteralPath $sidecarPath -PathType Leaf)) {
        Add-RerunAutoReviewIssue -Issues $issues -Code 'sidecar_missing' -Message 'Pipeline sidecar evidence is missing; output requires Pending Publish review.' -Evidence $sidecarPath
        return @($issues)
    }

    $pipelineSidecar = Read-RerunPipelineSidecar -OutputPath $VerifiedOutput
    if ($null -eq $pipelineSidecar) {
        Add-RerunAutoReviewIssue -Issues $issues -Code 'sidecar_unreadable' -Message 'Pipeline sidecar evidence could not be read; output requires Pending Publish review.' -Evidence $sidecarPath
        return @($issues)
    }

    $schema = Get-RerunObjectText -Object $pipelineSidecar -Name 'schema_version' -Default ''
    if ($schema -ne 'pipeline_sidecar.v1') {
        Add-RerunAutoReviewIssue -Issues $issues -Code 'sidecar_schema_untrusted' -Message 'Pipeline sidecar schema is not the expected pipeline_sidecar.v1 contract.' -Evidence $schema
    }

    $publishState = (Get-RerunObjectText -Object $pipelineSidecar -Name 'publish_state' -Default '').Trim().ToLowerInvariant()
    if (-not [string]::IsNullOrWhiteSpace($publishState) -and $publishState -ne 'published') {
        Add-RerunAutoReviewIssue -Issues $issues -Code 'publish_state_not_clean' -Message 'Nested pipeline publish state is not clean published evidence.' -Evidence $publishState
    }
    $publishMode = (Get-RerunObjectText -Object $pipelineSidecar -Name 'publish_mode' -Default '').Trim().ToLowerInvariant()
    if ($publishMode -match 'pending|deferred|review|retry|failed') {
        Add-RerunAutoReviewIssue -Issues $issues -Code 'publish_mode_requires_review' -Message 'Nested pipeline publish mode indicates deferred/review/retry handling.' -Evidence $publishMode
    }

    $actualSize = 0L
    try { $actualSize = [long](Get-Item -LiteralPath $VerifiedOutput -Force).Length } catch {}
    $sidecarSizeRaw = Get-RerunObjectValue -Object $pipelineSidecar -Name 'output_size' -Default $null
    $sidecarSize = $null
    try {
        if ($null -ne $sidecarSizeRaw) { $sidecarSize = [long]$sidecarSizeRaw }
    } catch {
        $sidecarSize = $null
    }
    if ($null -eq $sidecarSize) {
        Add-RerunAutoReviewIssue -Issues $issues -Code 'output_size_missing' -Message 'Pipeline sidecar output_size evidence is missing.' -Evidence $sidecarPath
    } elseif ($actualSize -gt 0 -and $sidecarSize -ne $actualSize) {
        Add-RerunAutoReviewIssue -Issues $issues -Code 'output_size_mismatch' -Message 'Pipeline sidecar output_size does not match the verified output file.' -Evidence ("sidecar={0}; actual={1}" -f $sidecarSize, $actualSize)
    }

    foreach ($failureField in @('tx3g_srt_failures','bdpgs_srt_failures','vobsub_srt_failures')) {
        $failures = @(Get-RerunArrayField -Object $pipelineSidecar -Name $failureField)
        if ($failures.Count -gt 0) {
            Add-RerunAutoReviewIssue -Issues $issues -Code $failureField -Message "Subtitle conversion failure evidence remains in $failureField." -Evidence ("count={0}" -f $failures.Count)
        }
    }

    foreach ($decision in @(Get-RerunArrayField -Object $pipelineSidecar -Name 'subtitle_decisions')) {
        $routesToReview = Get-RerunBoolField -Object $decision -Name 'routes_to_review'
        $reviewCode = Get-RerunObjectText -Object $decision -Name 'review_error_code' -Default ''
        $reviewReason = Get-RerunObjectText -Object $decision -Name 'review_reason' -Default ''
        if ($routesToReview -or -not [string]::IsNullOrWhiteSpace($reviewCode) -or -not [string]::IsNullOrWhiteSpace($reviewReason)) {
            $evidence = if (-not [string]::IsNullOrWhiteSpace($reviewCode)) { $reviewCode } else { $reviewReason }
            Add-RerunAutoReviewIssue -Issues $issues -Code 'subtitle_decision_requires_review' -Message 'Subtitle decision evidence requires operator review.' -Evidence $evidence
        }
    }

    foreach ($reviewField in @('issues','warnings','errors','review_issues','validation_issues')) {
        $fieldEvidence = @(Get-RerunArrayField -Object $pipelineSidecar -Name $reviewField)
        if ($fieldEvidence.Count -gt 0) {
            Add-RerunAutoReviewIssue -Issues $issues -Code ("sidecar_{0}" -f $reviewField) -Message "Pipeline sidecar contains $reviewField evidence; output requires Pending Publish review." -Evidence ("count={0}" -f $fieldEvidence.Count)
        }
    }
    foreach ($reviewFlag in @('requires_review','needs_review','operator_review_required')) {
        if (Get-RerunBoolField -Object $pipelineSidecar -Name $reviewFlag) {
            Add-RerunAutoReviewIssue -Issues $issues -Code ("sidecar_{0}" -f $reviewFlag) -Message "Pipeline sidecar sets $reviewFlag; output requires Pending Publish review." -Evidence 'true'
        }
    }

    $quality = Get-RerunObjectValue -Object $pipelineSidecar -Name 'quality_verification' -Default $null
    if ($null -ne $quality -and (Test-RerunObjectHasProperty -Object $quality -Name 'attempted') -and (Get-RerunBoolField -Object $quality -Name 'attempted')) {
        $qualityOutcome = (Get-RerunObjectText -Object $quality -Name 'outcome' -Default '').Trim().ToLowerInvariant()
        $qualityBlocked = Get-RerunBoolField -Object $quality -Name 'block_publish'
        if ($qualityBlocked -or $qualityOutcome -notin @('pass','passed')) {
            Add-RerunAutoReviewIssue -Issues $issues -Code 'quality_verification_not_clean' -Message 'Quality verification did not produce clean pass evidence.' -Evidence ("outcome={0}; block_publish={1}" -f $qualityOutcome, $qualityBlocked)
        }
    }

    $dynamicHdr = Get-RerunObjectValue -Object $pipelineSidecar -Name 'dynamic_hdr' -Default $null
    if ($null -ne $dynamicHdr) {
        $dynamicOutcome = (Get-RerunObjectText -Object $dynamicHdr -Name 'outcome' -Default '').Trim().ToLowerInvariant()
        $dynamicAction = (Get-RerunObjectText -Object $dynamicHdr -Name 'policy_action' -Default (Get-RerunObjectText -Object $dynamicHdr -Name 'action' -Default '')).Trim().ToLowerInvariant()
        $dynamicRoute = (Get-RerunObjectText -Object $dynamicHdr -Name 'recommended_route' -Default '').Trim().ToLowerInvariant()
        $dynamicError = Get-RerunObjectText -Object $dynamicHdr -Name 'error_code' -Default ''
        $dynamicReview = Get-RerunBoolField -Object $dynamicHdr -Name 'should_hold_review'
        $dynamicEvidence = @($dynamicOutcome, $dynamicAction, $dynamicRoute, $dynamicError) -join ';'
        if ($dynamicReview -or -not [string]::IsNullOrWhiteSpace($dynamicError) -or $dynamicEvidence -match 'blocked|failed|drop|warn|review|missing|unpreservable|unknown') {
            Add-RerunAutoReviewIssue -Issues $issues -Code 'dynamic_hdr_not_clean' -Message 'Dynamic HDR evidence is not clean replacement evidence.' -Evidence $dynamicEvidence
        }
    }

    return @($issues)
}

function Get-RerunStopAfterCurrentRequest {
    param(
        [string]$MarkerPath,
        [string]$BatchId,
        [string]$ManifestPath,
        [string]$CsvPath,
        [datetime]$StartedAtUtc
    )
    if ([string]::IsNullOrWhiteSpace($MarkerPath) -or -not (Test-Path -LiteralPath $MarkerPath -PathType Leaf)) {
        return $null
    }
    try {
        $marker = Get-Content -LiteralPath $MarkerPath -Raw | ConvertFrom-Json -ErrorAction Stop
    } catch {
        Write-RerunLog "Ignoring unreadable CSV rerun control marker: $MarkerPath ($($_.Exception.Message))" "WARN"
        return $null
    }
    if ((Get-RerunObjectText -Object $marker -Name 'action' -Default '') -ne 'stop_after_current') {
        return $null
    }
    $markerBatchId = Get-RerunObjectText -Object $marker -Name 'batch_id' -Default ''
    if (-not [string]::IsNullOrWhiteSpace($markerBatchId) -and $markerBatchId -ne $BatchId) {
        return $null
    }
    $markerManifestPath = Get-RerunObjectText -Object $marker -Name 'manifest_path' -Default ''
    if (-not [string]::IsNullOrWhiteSpace($markerManifestPath) -and (Get-RerunNormalizedPathKey -Path $markerManifestPath) -ne (Get-RerunNormalizedPathKey -Path $ManifestPath)) {
        return $null
    }
    $markerCsvPath = Get-RerunObjectText -Object $marker -Name 'csv_path' -Default ''
    if (-not [string]::IsNullOrWhiteSpace($markerCsvPath) -and (Get-RerunNormalizedPathKey -Path $markerCsvPath) -ne (Get-RerunNormalizedPathKey -Path $CsvPath)) {
        return $null
    }
    if ([string]::IsNullOrWhiteSpace($markerBatchId) -and [string]::IsNullOrWhiteSpace($markerManifestPath)) {
        $createdText = Get-RerunObjectText -Object $marker -Name 'created_at' -Default ''
        if (-not [string]::IsNullOrWhiteSpace($createdText)) {
            try {
                $createdAt = [datetimeoffset]::Parse($createdText).UtcDateTime
                if ($createdAt -lt $StartedAtUtc.AddSeconds(-5)) {
                    return $null
                }
            } catch {
                return $null
            }
        }
    }
    return $marker
}

function Update-RerunManifestCounts {
    param(
        $Manifest,
        [array]$Plans,
        [int]$PipelineExitFailures = 0
    )
    $review = @($Plans | Where-Object { $_.status -eq 'review_workspace' }).Count
    $pendingPublish = @($Plans | Where-Object { $_.status -eq 'pending_publish' }).Count
    $published = @($Plans | Where-Object { $_.status -in @('published_non_overlap','published_replace_final') }).Count
    $failed = @($Plans | Where-Object { $_.status -eq 'failed' }).Count
    $pending = @($Plans | Where-Object { $_.status -eq 'pending' }).Count
    $success = $review + $pendingPublish + $published
    $Manifest.pipeline_exit_failures = $PipelineExitFailures
    $Manifest.success_count = $success
    $Manifest.review_workspace_count = $review
    $Manifest.pending_publish_count = $pendingPublish
    $Manifest.published_count = $published
    $Manifest.failed_count = $failed
    $Manifest.remaining_pending_count = $pending
    return [pscustomobject][ordered]@{
        review = $review
        pending_publish = $pendingPublish
        published = $published
        failed = $failed
        pending = $pending
        success = $success
    }
}

function Get-RerunPendingServerDestinationSet {
    param([string]$PendingRoot)
    $set = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    if ([string]::IsNullOrWhiteSpace($PendingRoot) -or -not (Test-Path -LiteralPath $PendingRoot)) {
        return ,$set
    }
    foreach ($manifestFile in @(Get-ChildItem -LiteralPath $PendingRoot -File -Filter '*.manifest.json' -ErrorAction SilentlyContinue)) {
        try {
            $manifest = Get-Content -LiteralPath $manifestFile.FullName -Raw | ConvertFrom-Json -ErrorAction Stop
            $serverOut = [string](Get-RerunObjectValue -Object $manifest -Name 'server_out' -Default '')
            $key = Get-RerunNormalizedPathKey -Path $serverOut
            if (-not [string]::IsNullOrWhiteSpace($key)) {
                $set.Add($key) | Out-Null
            }
        } catch {
            Write-RerunLog "CSV rerun could not read pending manifest while checking destinations $($manifestFile.FullName): $($_.Exception.Message)" "WARN"
        }
    }
    return ,$set
}

function Copy-RerunRecordProperties {
    param($Record)
    $map = [ordered]@{}
    if ($null -eq $Record) { return $map }
    foreach ($prop in $Record.PSObject.Properties) {
        $map[$prop.Name] = $prop.Value
    }
    return $map
}

function New-RerunPendingSidecarEntries {
    param(
        $PipelineSidecar,
        [Parameter(Mandatory)] [string]$VerifiedOutput,
        [Parameter(Mandatory)] [string]$FinalOutput,
        [Parameter(Mandatory)] [string]$PendingRoot,
        [Parameter(Mandatory)] [string]$TransactionId,
        [string]$FinalOutputRoot = '',
        [switch]$AllowSourceOutputRoot
    )
    $entries = [System.Collections.Generic.List[object]]::new()
    $tracks = [System.Collections.Generic.List[object]]::new()
    $copied = [System.Collections.Generic.List[string]]::new()
    if ($null -eq $PipelineSidecar) {
        return [pscustomobject]@{ Entries = @(); Tracks = @(); Copied = @() }
    }

    $verifiedDir = Split-Path -Parent $VerifiedOutput
    $finalDir = Split-Path -Parent $FinalOutput
    $sidecarIndex = 0
    foreach ($record in @(Get-RerunArrayField -Object $PipelineSidecar -Name 'tx3g_srt_tracks')) {
        $source = Get-RerunTrackSourcePath -Record $record
        if ([string]::IsNullOrWhiteSpace($source)) { continue }
        if ([System.IO.Path]::GetExtension($source).ToLowerInvariant() -ne '.srt') { continue }
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { continue }
        if (-not (Test-RerunPathUnderRoot -Path $source -Root $verifiedDir)) { continue }

        $relative = [System.IO.Path]::GetRelativePath([System.IO.Path]::GetFullPath($verifiedDir), [System.IO.Path]::GetFullPath($source))
        if ([string]::IsNullOrWhiteSpace($relative) -or $relative.StartsWith('..')) { continue }
        $relativeParent = Split-Path $relative -Parent
        $relativeLeaf = Split-Path $relative -Leaf
        $sourceStem = [System.IO.Path]::GetFileNameWithoutExtension($relativeLeaf)
        $verifiedStem = [System.IO.Path]::GetFileNameWithoutExtension($VerifiedOutput)
        $finalStem = [System.IO.Path]::GetFileNameWithoutExtension($FinalOutput)
        if (-not [string]::IsNullOrWhiteSpace($verifiedStem) -and $sourceStem.StartsWith($verifiedStem, [System.StringComparison]::OrdinalIgnoreCase)) {
            $relativeLeaf = $finalStem + $sourceStem.Substring($verifiedStem.Length) + [System.IO.Path]::GetExtension($relativeLeaf)
        }
        $relativeServerPath = if ([string]::IsNullOrWhiteSpace($relativeParent)) { $relativeLeaf } else { Join-Path $relativeParent $relativeLeaf }
        $serverOut = Join-Path $finalDir $relativeServerPath
        if (-not (Test-RerunPathUnderRoot -Path $serverOut -Root $finalDir)) {
            throw "sidecar destination resolves outside final output folder: $serverOut"
        }
        if (-not $AllowSourceOutputRoot -and -not [string]::IsNullOrWhiteSpace($FinalOutputRoot) -and -not (Test-RerunPathUnderRoot -Path $serverOut -Root $FinalOutputRoot)) {
            throw "sidecar destination resolves outside configured output root: $serverOut"
        }
        $parked = Join-Path $PendingRoot ("{0}.sidecar{1}{2}" -f $TransactionId, $sidecarIndex, [System.IO.Path]::GetExtension($source))
        if (Test-Path -LiteralPath $parked) { $parked = Get-RerunNonOverlapPath -Path $parked -Suffix $TransactionId }
        try {
            Copy-Item -LiteralPath $source -Destination $parked -Force -ErrorAction Stop
        } catch {
            foreach ($copiedSidecar in @($copied)) {
                Remove-Item -LiteralPath $copiedSidecar -Force -ErrorAction SilentlyContinue
            }
            throw
        }
        $copied.Add($parked) | Out-Null

        $pendingRecord = Copy-RerunRecordProperties -Record $record
        $pendingRecord['path'] = $serverOut
        $pendingRecord['file_name'] = Split-Path -Leaf $serverOut
        $pendingRecord['status'] = 'pending'
        $tracks.Add([pscustomobject]$pendingRecord) | Out-Null
        $entries.Add([pscustomobject][ordered]@{
            kind = 'converted_srt'
            local_file = $parked
            original_local_file = $source
            parked_file = $parked
            server_out = $serverOut
            output_size = [long](Get-Item -LiteralPath $parked -Force).Length
            preserve_existing = [bool](Get-RerunObjectValue -Object $record -Name 'preserved_existing' -Default $false)
            tx3g_record = [pscustomobject]$pendingRecord
        }) | Out-Null
        $sidecarIndex++
    }
    return [pscustomobject]@{ Entries = @($entries); Tracks = @($tracks); Copied = @($copied) }
}

function Assert-RerunPendingPublishManifestContract {
    param($Payload)

    foreach ($key in @(
        'pipeline_version',
        'publish_transaction_id',
        'manifest_state',
        'local_file',
        'server_out',
        'route',
        'source_identity_v2',
        'source_identity_v2_algorithm',
        'source_path'
    )) {
        if ([string]::IsNullOrWhiteSpace([string]$Payload[$key])) {
            throw "CSV rerun pending manifest field is required and cannot be blank: $key"
        }
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
        if (-not $Payload.Contains($key)) {
            throw "CSV rerun pending manifest array field is required: $key"
        }
    }
    if ($null -eq $Payload['output_size']) {
        throw 'CSV rerun pending manifest output_size is required.'
    }
}

function Test-RerunSourceMatchesCsv {
    param(
        [System.IO.FileInfo]$FileInfo,
        $Row,
        [string]$FfprobePath
    )
    $expectedSize = Get-RerunValue -Row $Row -Names @('source_size','SourceSizeBytes','SizeBytes') -Default ''
    if ($expectedSize -match '^\d+$' -and [long]$expectedSize -ne [long]$FileInfo.Length) {
        return "source size changed: CSV=$expectedSize current=$($FileInfo.Length)"
    }

    $expectedMtime = Get-RerunValue -Row $Row -Names @('source_mtime_utc','SourceLastWriteUtc','LastWriteTimeUtc') -Default ''
    if ($expectedMtime) {
        try {
            $parsed = [datetimeoffset]::Parse($expectedMtime, [System.Globalization.CultureInfo]::InvariantCulture)
            $delta = [math]::Abs(($FileInfo.LastWriteTimeUtc - $parsed.UtcDateTime).TotalSeconds)
            if ($delta -gt 2) {
                return "source mtime changed: CSV=$expectedMtime current=$($FileInfo.LastWriteTimeUtc.ToString('o'))"
            }
        } catch {
            Write-RerunLog "Could not parse CSV source_mtime_utc '$expectedMtime' for $($FileInfo.FullName)" "WARN"
        }
    }

    $expectedIdentity = Get-RerunValue -Row $Row -Names @('source_identity_v2','SourceIdentityV2') -Default ''
    if ($expectedIdentity) {
        $currentIdentity = Get-RerunSourceIdentityV2 -FileInfo $FileInfo -FfprobePath $FfprobePath
        if (-not $currentIdentity) {
            return 'source identity v2 could not be recomputed'
        }
        if ($currentIdentity -ne $expectedIdentity) {
            return 'source identity v2 changed'
        }
    }
    return ''
}

function Get-RerunMediaKind {
    param($Row, [string]$Path)
    $kind = (Get-RerunValue -Row $Row -Names @('media_kind','MediaType') -Default '').Trim().ToLowerInvariant()
    if ($kind -in @('tv','show','episode')) { return 'TV' }
    if ($kind -in @('movie','movies','film')) { return 'Movie' }
    $parts = @($Path -split '[\\/]+') | ForEach-Object { $_.ToLowerInvariant() }
    if ($parts -contains 'tv') { return 'TV' }
    return 'Movie'
}

function Join-RerunPathParts {
    param([string[]]$Parts)
    $clean = @($Parts | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($clean.Count -eq 0) { return '' }
    $path = [string]$clean[0]
    for ($i = 1; $i -lt $clean.Count; $i++) { $path = Join-Path $path ([string]$clean[$i]) }
    return $path
}
