# ==============================================================================
# engine\failures\failure_state.ps1
# ==============================================================================
# Round-failure records, persistent failure markers, retry escalation, and
# failure-artifact preservation.
#
# Dot-sourced from MediaPipeline.ps1. Reads/writes at call time:
#   $LocalFailureReports, $LocalFailureMarkers, $LocalFailureArtifacts
#   $script:RoundFailureRecords, $script:FailureMarkerIndex
#   $script:TransientFailureRetryLimit, $script:SourceIdentityV2Algorithm
#
# Cross-module/main helpers:
#   Write-Log
#   Get-FFprobeFailureCode, Get-FFmpegFailureCode, Get-MkvmergeFailureCode
#   Get-SourceIdentityKey, Get-SourceIdentityKeyV2, Get-SafeLocalName
#   Remove-ScratchFingerprint
# ==============================================================================
function Get-FailureSuggestedAction {
    param(
        [string]$Stage,
        [string]$Reason
    )

    switch -Regex ($Stage) {
        '^tv-parse$'       { return 'Rename the source to include SxxEyy, NxM, or a strong episode token such as Episode 1 / Ep 1 / E01.' }
        '^remux-av$'       { return 'Inspect the FFmpeg stderr log and repro command, then retry once the source or tool issue is fixed.' }
        '^remux-mkvmerge$' { return 'Inspect the mkvmerge stderr log and repro command, then retry after fixing the subtitle/container issue.' }
        '^remux-verify$'   { return 'Compare source and local output A/V end times before retrying. Subtitle-tail container differences are tolerated now, so a remaining remux-verify failure usually means the output A/V is actually short.' }
        '^remux-push$'     { return 'Inspect network/share availability and free space; the verified local output is parked in PendingServerPush for retry.' }
        '^remux-sidecar$'  { return 'Inspect sidecar write permissions on the share; the verified local output is parked for retry.' }
        '^encode$'         { return 'Inspect the FFmpeg stderr log and repro command. If NVENC is unstable, check the CPU fallback result or run the saved repro manually.' }
        '^encode-verify$'  { return 'Compare source and encoded output durations before retrying; this usually means a truncated encode.' }
        '^encode-push$'    { return 'Inspect network/share availability and free space; the verified local output is parked in PendingServerPush for retry.' }
        '^encode-sidecar$' { return 'Inspect sidecar write permissions on the share; the verified local output is parked for retry.' }
        '^scratch-integrity$' { return 'Redownload or replace the source if ffprobe cannot read the original file; otherwise inspect the scratch disk and copy path before retrying.' }
        '^path-capability$' { return 'Shorten the source folder or filename, fix permissions, or enable long-path support for the target filesystem/share.' }
        '^path-limit$'      { return 'Shorten the source folder or filename, fix permissions, or enable long-path support for the target filesystem/share.' }
        default {
            if ($Reason) { return $Reason }
            return 'Inspect the failure artifact and logs, then retry.'
        }
    }
}

function Normalize-FailureCode {
    param([string]$Code)
    if ([string]::IsNullOrWhiteSpace($Code)) { return 'UNKNOWN_FAILURE' }
    $normalized = ([string]$Code).Trim().ToUpperInvariant() -replace '[^A-Z0-9]+','_'
    $normalized = $normalized.Trim('_')
    if ([string]::IsNullOrWhiteSpace($normalized)) { return 'UNKNOWN_FAILURE' }
    return $normalized
}

function Get-FailureCategory {
    param(
        [string]$Stage,
        [string]$ErrorCode
    )

    $stageText = if ($Stage) { ([string]$Stage).ToLowerInvariant() } else { '' }
    $codeText = if ($ErrorCode) {
        if (Get-Command -Name Normalize-FailureCode -ErrorAction SilentlyContinue) {
            Normalize-FailureCode -Code $ErrorCode
        } else {
            (([string]$ErrorCode).Trim().ToUpperInvariant() -replace '[^A-Z0-9]+','_').Trim('_')
        }
    } else { '' }

    if ($codeText -match 'TOOL_MISSING|TOOL_NOT_FOUND|OCR_TOOL_MISSING|ENCODER_UNAVAILABLE') { return 'tool_missing' }
    if ($stageText -match 'config|setup|schema' -or $codeText -match '^CONFIG_|CONFIGURATION|SCHEMA') { return 'config' }
    if ($stageText -match 'route|routing|classify' -or $codeText -match '^ROUTE_') { return 'route' }
    if ($stageText -match 'push|publish|sidecar' -or $codeText -match 'PUBLISH|SIDECAR') { return 'publish' }
    if ($stageText -match 'deferred|pending' -or $codeText -match 'PENDING|DEFERRED') { return 'deferred_publish' }
    if ($stageText -match '^subtitle-' -or $codeText -match '^SUBTITLE_') { return 'subtitle_conversion' }
    if ($stageText -match 'verify|validation|integrity' -or $codeText -match 'VALIDATION|DURATION_MISMATCH|SRT_EMPTY|SRT_INVALID') { return 'validation' }
    if ($stageText -match 'probe' -or $codeText -match 'PROBE|SOURCE_MEDIA|MEDIA_CONTAINER|MEDIA_TRUNCATED|MEDIA_STREAM') { return 'probe' }
    if ($stageText -match 'remux' -or $codeText -match '^REMUX_|MKVMERGE') { return 'remux' }
    if ($stageText -match 'encode' -or $codeText -match '^ENCODE_|NVENC|ENCODER') { return 'encode' }
    if ($stageText -match 'path|file|disk|copy|move' -or $codeText -match 'FILE_|PATH|DISK|ACCESS_DENIED|FILESYSTEM') { return 'filesystem' }
    return 'validation'
}

function New-StandardFailureRecord {
    param(
        [string] $SourcePath = '',
        [string] $Stage = '',
        [string] $Reason = '',
        [string] $Classification = 'transient',
        [string] $ErrorCode = $null,
        [string] $Category = $null,
        [string] $Operation = $null,
        [string] $Tool = $null,
        [object] $ExitCode = $null,
        [object] $Retryable = $null,
        [string] $ArtifactPath = $null,
        [string] $SuggestedAction = $null,
        [string] $SuggestedRename = $null,
        [string] $ReproPath = $null,
        [int] $RetryCount = 0,
        [int] $RetryLimit = 0,
        [bool] $Escalated = $false,
        [string] $JobId = $null,
        [string] $CorrelationId = $null,
        [hashtable] $AdditionalProperties = @{}
    )

    $resolvedCode = if ($ErrorCode) {
        $ErrorCode
    } elseif (Get-Command -Name Get-MediaFailureCode -ErrorAction SilentlyContinue) {
        Get-MediaFailureCode -Stage $Stage -Reason $Reason -Classification $Classification
    } else {
        'UNKNOWN_FAILURE'
    }
    $resolvedCode = if (Get-Command -Name Normalize-FailureCode -ErrorAction SilentlyContinue) {
        Normalize-FailureCode -Code $resolvedCode
    } else {
        (([string]$resolvedCode).Trim().ToUpperInvariant() -replace '[^A-Z0-9]+','_').Trim('_')
    }
    if ([string]::IsNullOrWhiteSpace($resolvedCode)) { $resolvedCode = 'UNKNOWN_FAILURE' }

    $resolvedCategory = if ($Category) { $Category } else { Get-FailureCategory -Stage $Stage -ErrorCode $resolvedCode }
    $resolvedOperation = if ($Operation) { $Operation } else { $Stage }
    $operatorAction = if ($SuggestedAction) {
        $SuggestedAction
    } elseif (Get-Command -Name Get-FailureSuggestedAction -ErrorAction SilentlyContinue) {
        Get-FailureSuggestedAction -Stage $Stage -Reason $Reason
    } elseif ($Reason) {
        $Reason
    } else {
        'Inspect the failure artifact and logs, then retry.'
    }

    $retryableValue = if ($null -ne $Retryable) {
        [bool]$Retryable
    } else {
        ([string]$Classification -eq 'transient')
    }
    $resolvedJobId = if ($JobId) { $JobId } elseif ($script:CurrentJobId) { [string]$script:CurrentJobId } else { '' }
    $resolvedCorrelationId = if ($CorrelationId) { $CorrelationId } elseif ($script:PipelineRunId) { [string]$script:PipelineRunId } else { '' }
    $recordedAt = (Get-Date).ToString('o')

    $record = [ordered]@{
        SchemaVersion    = 'failure_record.v1'
        schema_version   = 'failure_record.v1'
        category         = $resolvedCategory
        SourcePath       = $SourcePath
        source_path      = $SourcePath
        JobId            = $resolvedJobId
        job_id           = $resolvedJobId
        CorrelationId    = $resolvedCorrelationId
        correlation_id   = $resolvedCorrelationId
        operation        = $resolvedOperation
        stage            = $Stage
        ErrorCode        = $resolvedCode
        error_code       = $resolvedCode
        reason           = $Reason
        classification   = $Classification
        tool             = $Tool
        ExitCode         = $ExitCode
        exit_code        = $ExitCode
        retryable        = $retryableValue
        ArtifactPath     = $ArtifactPath
        artifact_path    = $ArtifactPath
        SuggestedAction  = $operatorAction
        suggested_action = $operatorAction
        OperatorAction   = $operatorAction
        operator_action  = $operatorAction
        SuggestedRename  = $SuggestedRename
        suggested_rename = $SuggestedRename
        ReproPath        = $ReproPath
        repro_path       = $ReproPath
        ReproductionPath = $ReproPath
        reproduction_path = $ReproPath
        RetryCount       = $RetryCount
        retry_count      = $RetryCount
        RetryLimit       = $RetryLimit
        retry_limit      = $RetryLimit
        escalated        = $Escalated
        RecordedAt       = $recordedAt
        recorded_at      = $recordedAt
    }

    if ($AdditionalProperties) {
        foreach ($key in @($AdditionalProperties.Keys)) {
            if ([string]::IsNullOrWhiteSpace([string]$key)) { continue }
            $record[$key] = $AdditionalProperties[$key]
        }
    }
    return [pscustomobject]$record
}

function Get-SourceIntegrityFailureCode {
    param([object]$IntegrityResult)

    $code = if ($IntegrityResult -and $IntegrityResult.PSObject.Properties['ErrorCode']) { [string]$IntegrityResult.ErrorCode } else { '' }
    switch ($code) {
        'FILE_PATH_EMPTY'             { return 'SOURCE_FILE_PATH_EMPTY' }
        'FILE_MISSING'                { return 'SOURCE_FILE_MISSING' }
        'FILE_ZERO_BYTES'             { return 'SOURCE_FILE_ZERO_BYTES' }
        'MEDIA_PROBE_TIMEOUT'         { return 'SOURCE_MEDIA_PROBE_TIMEOUT' }
        'MEDIA_PROBE_STOPPED'         { return 'SOURCE_MEDIA_PROBE_STOPPED' }
        'MEDIA_CONTAINER_INVALID'     { return 'SOURCE_MEDIA_CONTAINER_INVALID' }
        'MEDIA_TRUNCATED'             { return 'SOURCE_MEDIA_TRUNCATED' }
        'MEDIA_ACCESS_DENIED'         { return 'SOURCE_MEDIA_ACCESS_DENIED' }
        'MEDIA_STREAM_UNSUPPORTED'    { return 'SOURCE_MEDIA_STREAM_UNSUPPORTED' }
        'MEDIA_DURATION_MISSING'      { return 'SOURCE_MEDIA_DURATION_MISSING' }
        'MEDIA_INTEGRITY_EXCEPTION'   { return 'SOURCE_MEDIA_INTEGRITY_EXCEPTION' }
        'MEDIA_PROBE_FAILED'          { return 'SOURCE_MEDIA_PROBE_FAILED' }
        default                       { return 'SOURCE_MEDIA_UNREADABLE' }
    }
}

function Get-MediaFailureCode {
    param(
        [string]$Stage,
        [string]$Reason,
        [string]$Classification = 'transient'
    )

    $stageText = if ($Stage) { $Stage } else { '' }
    $reasonText = if ($Reason) { $Reason } else { '' }
    $combined = ("$stageText $reasonText").ToLowerInvariant()

    if ($combined -match 'source integrity failed') {
        $ffprobeCode = Get-FFprobeFailureCode -ErrorText $reasonText
        if ($ffprobeCode -eq 'MEDIA_CONTAINER_INVALID') { return 'SOURCE_MEDIA_CONTAINER_INVALID' }
        if ($ffprobeCode -eq 'MEDIA_TRUNCATED') { return 'SOURCE_MEDIA_TRUNCATED' }
        if ($ffprobeCode -eq 'MEDIA_ACCESS_DENIED') { return 'SOURCE_MEDIA_ACCESS_DENIED' }
        if ($ffprobeCode -eq 'MEDIA_STREAM_UNSUPPORTED') { return 'SOURCE_MEDIA_STREAM_UNSUPPORTED' }
        if ($ffprobeCode -eq 'FILE_MISSING') { return 'SOURCE_FILE_MISSING' }
        return 'SOURCE_MEDIA_UNREADABLE'
    }

    switch -Regex ($stageText) {
        '^tv-parse$'                 { return 'SOURCE_TV_PARSE_FAILED' }
        '^scratch-integrity$'        { return 'SCRATCH_INTEGRITY_FAILED' }
        '^remux-av$'                 { return Get-FFmpegFailureCode -Stage $stageText -ErrorText $reasonText }
        '^remux-mkvmerge$'           { if ($combined -match 'missing|empty') { return 'REMUX_OUTPUT_MISSING' }; return Get-MkvmergeFailureCode -ErrorText $reasonText }
        '^remux-verify$'             { return 'REMUX_DURATION_MISMATCH' }
        '^remux-push$'               { return 'PUBLISH_COPY_FAILED' }
        '^remux-sidecar$'            { return 'SIDECAR_WRITE_FAILED' }
        '^encode$'                   { if ($combined -match 'missing|empty') { return 'ENCODE_OUTPUT_MISSING' }; return Get-FFmpegFailureCode -Stage $stageText -ErrorText $reasonText }
        '^encode-verify$'            { return 'ENCODE_DURATION_MISMATCH' }
        '^encode-push$'              { return 'PUBLISH_COPY_FAILED' }
        '^encode-sidecar$'           { return 'SIDECAR_WRITE_FAILED' }
        '^subtitle-probe$'           { if ($combined -match 'json') { return 'SUBTITLE_PROBE_JSON_INVALID' }; return 'SUBTITLE_PROBE_FAILED' }
        '^subtitle-tx3g-extract$'    { if ($combined -match 'timeout') { return 'SUBTITLE_TX3G_EXTRACT_TIMEOUT' }; return 'SUBTITLE_TX3G_EXTRACT_FAILED' }
        '^subtitle-tx3g-publish$'    { return 'SUBTITLE_TX3G_SRT_PUBLISH_FAILED' }
        '^subtitle-vobsub-extract$'  { if ($combined -match 'tool|mkvextract') { return 'SUBTITLE_VOBSUB_EXTRACT_TOOL_MISSING' }; return 'SUBTITLE_VOBSUB_EXTRACT_FAILED' }
        '^subtitle-vobsub-ocr$'      { if ($combined -match 'tesseract') { return 'SUBTITLE_VOBSUB_TESSERACT_MISSING' }; if ($combined -match 'tool|seconv') { return 'SUBTITLE_VOBSUB_OCR_TOOL_MISSING' }; return 'SUBTITLE_VOBSUB_OCR_FAILED' }
        'deferred-publish'           { return 'PENDING_PARK_FAILED' }
        '^path-capability$|^path-limit$' { return 'OUTPUT_PATH_UNSUPPORTED' }
        '^remux-exception$'          { return 'REMUX_UNEXPECTED_EXCEPTION' }
        '^encode-exception$'         { return 'ENCODE_UNEXPECTED_EXCEPTION' }
    }

    if ($combined -match 'ffprobe.*timed out|timeout') { return 'MEDIA_PROBE_TIMEOUT' }
    if ($combined -match 'zero bytes') { return 'FILE_ZERO_BYTES' }
    if ($combined -match 'does not exist|not found|no such file') { return 'FILE_MISSING' }
    if ($combined -match 'ebml|moov atom|invalid data') { return 'MEDIA_CONTAINER_INVALID' }

    if ([string]$Classification -eq 'operator_required') { return 'OPERATOR_REQUIRED' }
    if ([string]$Classification -eq 'permanent') { return 'PERMANENT_FAILURE' }
    return 'TRANSIENT_FAILURE'
}

function Add-RoundFailureRecord {
    param(
        [string] $SourcePath = '',
        [string] $Stage = '',
        [string] $Reason = 'Failure reported without details',
        [string] $Classification = 'transient',
        [string] $ErrorCode = $null,
        [string] $ArtifactPath = $null,
        [string] $SuggestedAction = $null,
        [string] $SuggestedRename = $null,
        [string] $ReproPath = $null,
        [int] $RetryCount = 0,
        [int] $RetryLimit = 0,
        [bool] $Escalated = $false
    )

    if (-not $script:RoundFailureRecords) {
        $script:RoundFailureRecords = [System.Collections.Generic.List[psobject]]::new()
    }

    $failureRecord = New-StandardFailureRecord -SourcePath $SourcePath -Stage $Stage -Reason $Reason -Classification $Classification -ErrorCode $ErrorCode -ArtifactPath $ArtifactPath -SuggestedAction $SuggestedAction -SuggestedRename $SuggestedRename -ReproPath $ReproPath -RetryCount $RetryCount -RetryLimit $RetryLimit -Escalated:$Escalated
    $resolvedCode = $failureRecord.ErrorCode
    $script:RoundFailureRecords.Add($failureRecord)

    if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
        Write-PipelineEvent -EventType 'failure_recorded' -Stage $Stage -Status $Classification -SourcePath $SourcePath -Data @{
            schema_version   = $failureRecord.schema_version
            category         = $failureRecord.category
            operation        = $failureRecord.operation
            error_code       = $resolvedCode
            reason           = $Reason
            classification   = $Classification
            retryable        = $failureRecord.retryable
            artifact_path    = $ArtifactPath
            suggested_action = $failureRecord.SuggestedAction
            operator_action  = $failureRecord.OperatorAction
            suggested_rename = $SuggestedRename
            repro_path       = $ReproPath
            reproduction_path = $failureRecord.ReproductionPath
            job_id           = $failureRecord.JobId
            correlation_id   = $failureRecord.CorrelationId
            retry_count      = $RetryCount
            retry_limit      = $RetryLimit
            escalated        = $Escalated
        } | Out-Null
    }
}

function Write-FailureJsonAtomic {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] $InputObject,
        [int] $Depth = 5
    )

    $dir = Split-Path $Path -Parent
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $leaf = Split-Path $Path -Leaf
    $id = [guid]::NewGuid().ToString('N')
    $tmp = Join-Path $dir ".$leaf.$id.tmp"
    $backup = Join-Path $dir ".$leaf.$id.bak"
    try {
        # Use -InputObject (not pipeline) so a single-element array is not
        # enumerated into a bare object by ConvertTo-Json. The caller wraps
        # array payloads in @() at the call site; scalar payloads (marker
        # files) are passed directly and still serialise as JSON objects.
        $json = ConvertTo-Json -InputObject $InputObject -Depth $Depth
        [System.IO.File]::WriteAllText($tmp, $json, [System.Text.UTF8Encoding]::new($false))
        $null = Get-Content -LiteralPath $tmp -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop

        if ([System.IO.File]::Exists($Path)) {
            [System.IO.File]::Replace($tmp, $Path, $backup, $true)
            Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        } else {
            [System.IO.File]::Move($tmp, $Path)
        }
        return $true
    } catch {
        if ($tmp -and (Test-Path -LiteralPath $tmp)) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
        if ($backup -and (Test-Path -LiteralPath $backup)) {
            Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        }
        throw
    }
}

function Write-RoundFailureSummary {
    if (-not $script:RoundFailureRecords -or $script:RoundFailureRecords.Count -eq 0) {
        return $null
    }

    try {
        if (-not (Test-Path -LiteralPath $LocalFailureReports)) {
            New-Item -ItemType Directory -Path $LocalFailureReports -Force | Out-Null
        }

        $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $textPath  = Join-Path $LocalFailureReports "round_failures_${timestamp}.txt"
        $jsonPath  = Join-Path $LocalFailureReports "round_failures_${timestamp}.json"

        $sb = [System.Text.StringBuilder]::new()
        [void]$sb.AppendLine("MediaPipeline round failure summary")
        [void]$sb.AppendLine("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
        [void]$sb.AppendLine("")

        $entryNumber = 0
        foreach ($failure in $script:RoundFailureRecords) {
            $entryNumber++
            [void]$sb.AppendLine(("{0}. {1}" -f $entryNumber, $failure.SourcePath))
            [void]$sb.AppendLine(("   Stage          : {0}" -f $failure.Stage))
            [void]$sb.AppendLine(("   Error code     : {0}" -f $failure.ErrorCode))
            [void]$sb.AppendLine(("   Classification : {0}" -f $failure.Classification))
            if ($failure.RetryCount -gt 0 -or $failure.Escalated) {
                [void]$sb.AppendLine(("   Retry count    : {0}/{1}" -f $failure.RetryCount, $failure.RetryLimit))
            }
            if ($failure.Escalated) { [void]$sb.AppendLine("   Escalated      : true") }
            [void]$sb.AppendLine(("   Reason         : {0}" -f $failure.Reason))
            if ($failure.ArtifactPath)    { [void]$sb.AppendLine(("   Artifact       : {0}" -f $failure.ArtifactPath)) }
            if ($failure.ReproPath)       { [void]$sb.AppendLine(("   Repro command  : {0}" -f $failure.ReproPath)) }
            if ($failure.SuggestedRename) { [void]$sb.AppendLine(("   Suggested name : {0}" -f $failure.SuggestedRename)) }
            if ($failure.SuggestedAction) { [void]$sb.AppendLine(("   Action         : {0}" -f $failure.SuggestedAction)) }
            [void]$sb.AppendLine("")
        }

        [System.IO.File]::WriteAllText($textPath, $sb.ToString(), [System.Text.UTF8Encoding]::new($false))
        # @() forces a single-record collection to remain a JSON array, not
        # a bare object, so the Python reader always sees a list.
        Write-FailureJsonAtomic -Path $jsonPath -InputObject @($script:RoundFailureRecords) -Depth 5 | Out-Null
        return @{
            TextPath = $textPath
            JsonPath = $jsonPath
        }
    } catch {
        Write-Log "Could not write round failure summary: $_" "WARN"
        return $null
    }
}

function Get-SourceFailureMarkerPath {
    param($SourceFile)
    $key = Get-SourceIdentityKey $SourceFile
    if (-not $key) { return $null }
    return Join-Path $LocalFailureMarkers "$key.json"
}

function Get-SourceFailureMarkerPathV2 {
    param($SourceFile)
    $key = Get-SourceIdentityKeyV2 $SourceFile
    if (-not $key) { return $null }
    return Join-Path $LocalFailureMarkers "$key.json"
}

function Test-FailureMarkerMatchesCurrentSource {
    param(
        $MarkerPayload,
        $SourceFile
    )

    if ($null -eq $MarkerPayload -or $null -eq $SourceFile) { return $false }
    $markerSourceV2 = [string]$MarkerPayload.source_identity_v2
    if ([string]::IsNullOrWhiteSpace($markerSourceV2)) {
        return $true
    }

    $currentSourceV2 = Get-SourceIdentityKeyV2 $SourceFile
    if ($currentSourceV2 -eq $markerSourceV2) {
        return $true
    }

    Write-Log "Ignoring stale failure marker for $($SourceFile.FullName): source_identity_v2 changed" "INFO"
    return $false
}

function Get-SourceFailureArtifactPath {
    param($SourceFile, [string]$ScratchPath = $null)
    $key = Get-SourceIdentityKey $SourceFile
    if (-not $key) { return $null }
    $leaf = if ($ScratchPath) { Split-Path $ScratchPath -Leaf } else { Get-SafeLocalName $SourceFile.Name }
    return Join-Path $LocalFailureArtifacts "${key}__$leaf"
}

function Invalidate-FailureMarkerIndex {
    $script:FailureMarkerIndex = $null
}

function Get-FailureMarkerIndex {
    if ($script:FailureMarkerIndex) { return $script:FailureMarkerIndex }
    $index = @{
        Count              = 0
        BySourcePath       = @{}
        BySourceIdentityV2 = @{}
    }
    if (Test-Path -LiteralPath $LocalFailureMarkers -ErrorAction SilentlyContinue) {
        foreach ($marker in @(Get-ChildItem -LiteralPath $LocalFailureMarkers -File -Filter '*.json' -ErrorAction SilentlyContinue)) {
            try {
                $payload = Get-Content -LiteralPath $marker.FullName -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
                $index.Count++
                $sourcePath = [string]$payload.source_full_path
                if (-not [string]::IsNullOrWhiteSpace($sourcePath)) {
                    $sourceSize = $null
                    try { if ($null -ne $payload.source_size) { $sourceSize = [long]$payload.source_size } } catch {}
                    $index.BySourcePath[$sourcePath.ToLowerInvariant()] = @{
                        MarkerPath = $marker.FullName
                        SourceSize = $sourceSize
                    }
                }
                $sourceV2 = [string]$payload.source_identity_v2
                if (-not [string]::IsNullOrWhiteSpace($sourceV2)) {
                    $index.BySourceIdentityV2[$sourceV2] = $marker.FullName
                }
            } catch {
                Write-Log "Could not index failure marker $($marker.Name): $_" "WARN"
            }
        }
    }
    $script:FailureMarkerIndex = $index
    return $index
}

function Get-SourceFailureState {
    param($SourceFile)
    $markerPath = Get-SourceFailureMarkerPath $SourceFile
    if ($markerPath -and (Test-Path -LiteralPath $markerPath)) {
        try {
            $payload = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
            if (Test-FailureMarkerMatchesCurrentSource -MarkerPayload $payload -SourceFile $SourceFile) {
                return $payload
            }
        } catch {
            Write-Log "Could not read failure marker for $($SourceFile.FullName): $_" "WARN"
            return $null
        }
    }

    try {
        $index = Get-FailureMarkerIndex
        if (-not $index -or [int]$index.Count -le 0) { return $null }

        $pathKey = ([string]$SourceFile.FullName).ToLowerInvariant()
        if ($index.BySourcePath.ContainsKey($pathKey)) {
            $entry = $index.BySourcePath[$pathKey]
            $expectedSize = $entry['SourceSize']
            if ($null -eq $expectedSize -or [long]$SourceFile.Length -eq [long]$expectedSize) {
                $payload = Get-Content -LiteralPath ([string]$entry['MarkerPath']) -Raw | ConvertFrom-Json
                if (Test-FailureMarkerMatchesCurrentSource -MarkerPayload $payload -SourceFile $SourceFile) {
                    return $payload
                }
            }
        }

        if ($index.BySourceIdentityV2.Count -gt 0) {
            $markerPathV2 = Get-SourceFailureMarkerPathV2 $SourceFile
            if ($markerPathV2 -and (Test-Path -LiteralPath $markerPathV2 -ErrorAction SilentlyContinue)) {
                $payload = Get-Content -LiteralPath $markerPathV2 -Raw | ConvertFrom-Json
                if (Test-FailureMarkerMatchesCurrentSource -MarkerPayload $payload -SourceFile $SourceFile) {
                    return $payload
                }
            }
            $sourceV2 = Get-SourceIdentityKeyV2 $SourceFile
            if ($sourceV2 -and $index.BySourceIdentityV2.ContainsKey($sourceV2)) {
                $payload = Get-Content -LiteralPath ([string]$index.BySourceIdentityV2[$sourceV2]) -Raw | ConvertFrom-Json
                if (Test-FailureMarkerMatchesCurrentSource -MarkerPayload $payload -SourceFile $SourceFile) {
                    return $payload
                }
            }
        }
        return $null
    } catch {
        Write-Log "Could not read failure marker for $($SourceFile.FullName): $_" "WARN"
        return $null
    }
}

function Clear-SourceFailureState {
    param($SourceFile)
    $markerPath = Get-SourceFailureMarkerPath $SourceFile
    if ($markerPath -and (Test-Path -LiteralPath $markerPath)) {
        Remove-Item -LiteralPath $markerPath -Force -ErrorAction SilentlyContinue
    }
    try {
        $index = Get-FailureMarkerIndex
        $pathKey = ([string]$SourceFile.FullName).ToLowerInvariant()
        if ($index.BySourcePath.ContainsKey($pathKey)) {
            $indexedPath = [string]$index.BySourcePath[$pathKey]['MarkerPath']
            if ($indexedPath -and (Test-Path -LiteralPath $indexedPath -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath $indexedPath -Force -ErrorAction SilentlyContinue
            }
        }
        if ($index.BySourceIdentityV2.Count -gt 0) {
            $markerPathV2 = Get-SourceFailureMarkerPathV2 $SourceFile
            if ($markerPathV2 -and (Test-Path -LiteralPath $markerPathV2 -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath $markerPathV2 -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {}
    Invalidate-FailureMarkerIndex
}

function Write-SourceFailureState {
    param(
        $SourceFile,
        [ValidateSet('transient','permanent','operator_required')] [string] $Classification,
        [string] $Reason,
        [string] $Stage = '',
        [string] $ArtifactPath = $null,
        [string] $ErrorCode = $null,
        [int] $RetryCount = 0,
        [int] $RetryLimit = 0,
        [bool] $Escalated = $false,
        [string] $SuggestedAction = $null,
        [string] $SuggestedRename = $null,
        [string] $ReproPath = $null
    )

    $markerPath = Get-SourceFailureMarkerPath $SourceFile
    if (-not $markerPath) { return }
    if (-not (Test-Path -LiteralPath $LocalFailureMarkers)) {
        New-Item -ItemType Directory -Path $LocalFailureMarkers -Force | Out-Null
    }

    $standardFailure = New-StandardFailureRecord -SourcePath $SourceFile.FullName -Stage $Stage -Reason $Reason -Classification $Classification -ErrorCode $ErrorCode -ArtifactPath $ArtifactPath -SuggestedAction $SuggestedAction -SuggestedRename $SuggestedRename -ReproPath $ReproPath -RetryCount $RetryCount -RetryLimit $RetryLimit -Escalated:$Escalated
    $resolvedCode = $standardFailure.ErrorCode
    $sourceIdentity = Get-SourceIdentityKey $SourceFile
    $sourceIdentityV2 = Get-SourceIdentityKeyV2 $SourceFile
    $payload = [ordered]@{
        schema_version   = $standardFailure.schema_version
        category         = $standardFailure.category
        operation        = $standardFailure.operation
        source_path      = $standardFailure.source_path
        job_id           = $standardFailure.job_id
        correlation_id   = $standardFailure.correlation_id
        classification   = $Classification
        error_code       = $resolvedCode
        reason           = $Reason
        stage            = $Stage
        tool             = $standardFailure.tool
        exit_code        = $standardFailure.exit_code
        retryable        = $standardFailure.retryable
        operator_action  = $standardFailure.operator_action
        reproduction_path = $standardFailure.reproduction_path
        recorded_at      = $standardFailure.recorded_at
        source_identity  = $sourceIdentity
        source_identity_v2 = $sourceIdentityV2
        source_identity_v2_algorithm = $script:SourceIdentityV2Algorithm
        source_full_path = $SourceFile.FullName
        source_size      = $SourceFile.Length
        source_mtime_utc = $SourceFile.LastWriteTimeUtc.ToString('o')
        artifact_path    = $ArtifactPath
        retry_count      = $RetryCount
        retry_limit      = $RetryLimit
        escalated        = $Escalated
        suggested_action = $SuggestedAction
        suggested_rename = $SuggestedRename
        repro_path       = $ReproPath
    }

    try {
        Write-FailureJsonAtomic -Path $markerPath -InputObject $payload -Depth 4 | Out-Null
        Invalidate-FailureMarkerIndex
    } catch {
        Write-Log "Could not write failure marker for $($SourceFile.FullName): $_" "WARN"
    }
}

function Register-SourceFailure {
    param(
        $SourceFile,
        [string] $ScratchPath = $null,
        [ValidateSet('transient','permanent','operator_required')] [string] $Classification = 'transient',
        [string] $Reason,
        [string] $Stage = '',
        [string] $ErrorCode = $null,
        [string] $SuggestedAction = $null,
        [string] $SuggestedRename = $null,
        [string] $ReproPath = $null
    )

    $resolvedCode = if ($ErrorCode) { $ErrorCode } else { Get-MediaFailureCode -Stage $Stage -Reason $Reason -Classification $Classification }
    $resolvedCode = Normalize-FailureCode -Code $resolvedCode
    $retryLimit = [int]$script:TransientFailureRetryLimit
    if ($retryLimit -lt 1) { $retryLimit = 3 }
    $retryCount = 0
    $escalated = $false

    $existing = Get-SourceFailureState $SourceFile
    $existingRetryCount = 0
    if ($existing -and $existing.PSObject.Properties['retry_count']) {
        try { $existingRetryCount = [math]::Max(0, [int]$existing.retry_count) } catch { $existingRetryCount = 0 }
    }

    if ($Classification -eq 'transient') {
        $existingCode = if ($existing -and $existing.PSObject.Properties['error_code']) {
            Normalize-FailureCode -Code ([string]$existing.error_code)
        } else { '' }
        $existingStage = if ($existing -and $existing.PSObject.Properties['stage']) { [string]$existing.stage } else { '' }
        if ($existing -and $existingCode -eq $resolvedCode -and $existingStage -eq $Stage) {
            $retryCount = $existingRetryCount + 1
        } else {
            $retryCount = 1
        }

        if ($retryCount -ge $retryLimit) {
            $Classification = 'operator_required'
            $escalated = $true
            $baseAction = if ($SuggestedAction) { $SuggestedAction } else { Get-FailureSuggestedAction -Stage $Stage -Reason $Reason }
            $SuggestedAction = ($baseAction.TrimEnd() + " Retry limit $retryLimit reached; fix the root cause, then use Clear Errors or remove the marker before retrying.").Trim()
        }
    } else {
        $retryCount = $existingRetryCount
        if ($Classification -eq 'operator_required') { $escalated = $true }
    }

    $artifactPath = $null
    if ($ScratchPath -and (Test-Path -LiteralPath $ScratchPath)) {
        try {
            if (-not (Test-Path -LiteralPath $LocalFailureArtifacts)) {
                New-Item -ItemType Directory -Path $LocalFailureArtifacts -Force | Out-Null
            }
            $artifactPath = Get-SourceFailureArtifactPath -SourceFile $SourceFile -ScratchPath $ScratchPath
            if (Test-Path -LiteralPath $artifactPath) {
                Remove-Item -LiteralPath $artifactPath -Force -ErrorAction SilentlyContinue
            }
            Move-Item -LiteralPath $ScratchPath -Destination $artifactPath -Force
            Remove-ScratchFingerprint $ScratchPath
            Write-Log "Captured failure artifact: $artifactPath" "DEBUG"
        } catch {
            Write-Log "Could not preserve failure artifact for $($SourceFile.FullName): $_" "WARN"
            $artifactPath = $null
        }
    }

    $retryText = if ($retryCount -gt 0) { " retry=$retryCount/$retryLimit" } else { "" }
    Write-Log "Failure recorded [$resolvedCode] stage=$Stage classification=$Classification$retryText source=$($SourceFile.FullName)" "ERROR"
    Write-SourceFailureState -SourceFile $SourceFile -Classification $Classification -Reason $Reason -Stage $Stage -ArtifactPath $artifactPath -ErrorCode $resolvedCode -RetryCount $retryCount -RetryLimit $retryLimit -Escalated:$escalated -SuggestedAction $SuggestedAction -SuggestedRename $SuggestedRename -ReproPath $ReproPath
    Add-RoundFailureRecord -SourcePath $SourceFile.FullName -Stage $Stage -Reason $Reason -Classification $Classification -ErrorCode $resolvedCode -ArtifactPath $artifactPath -SuggestedAction $SuggestedAction -SuggestedRename $SuggestedRename -ReproPath $ReproPath -RetryCount $retryCount -RetryLimit $retryLimit -Escalated:$escalated
    return $artifactPath
}
