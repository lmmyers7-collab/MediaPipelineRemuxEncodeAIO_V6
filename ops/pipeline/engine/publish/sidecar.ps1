# ==============================================================================
# Modules\Sidecar.ps1
# ==============================================================================
# .pipeline.json sidecar + completed_jobs.jsonl manifest helpers extracted
# from MediaPipeline.ps1.
#
# Dot-sourced from the main script. Reads the following at call time:
#
#   $script:PipelineVersion       — current pipeline version stamp
#   $script:MinPipelineVersion    — minimum acceptable version (reprocess gate)
#   $script:ReprocessAll          — global reprocess override (debug toggle)
#   $LocalCompleted               — local Completed\ directory
#   $CompletedJobsManifest        — JSONL manifest path
#   Write-Log                     — Modules\Logging.ps1
#   Start-StopAwareSleep          — Modules\Native.ps1 (retry sleep)
#   Compare-PipelineVersion       — Modules\PathHelpers.ps1
#   Get-SourceIdentityKey,
#   Get-SourceIdentityKeyV2,
#   Test-LegacySourceIdentityV2Algorithm
#                                 — Modules\SourceIdentity.ps1
#
# Conceptual model:
#
#   Sidecar (next to output, on the outsource share)
#     "<Title>.mkv"            ← the encoded/remuxed media file
#     "<Title>.pipeline.json"  ← sidecar; canonical truth for "what produced this"
#
#   Completed-jobs manifest (LOCAL, append-only JSONL)
#     LocalBase\State\Completed\completed_jobs.jsonl
#     One line per successful publish. Read-optimised mirror for the
#     desktop UI's Completed tab — walking the SMB outsource tree to
#     enumerate sidecars proved unacceptably slow.
#
# Reprocess decision flow (Test-OutputNeedsReprocess):
#
#                  ReprocessAll=true ─→ TRUE
#                  no sidecar         ─→ TRUE  (legacy output)
#                  sidecar version < MinPipelineVersion ─→ TRUE
#                  output size on disk != sidecar.output_size ─→ TRUE
#                                                 (catches truncated /
#                                                  replaced outputs that
#                                                  still have a stale sidecar)
#                  source size mismatch ─→ TRUE
#                  source_identity_v2 mismatch ─→ TRUE
#                                                 (unless legacy v2 algorithm
#                                                  + source_identity matches)
#                  source_identity mismatch (no v2) ─→ TRUE
#                  no identity at all ─→ TRUE
#                  default ─→ FALSE
# ==============================================================================

# Sidecar lives next to the output file: "Foo.mkv" -> "Foo.pipeline.json"
function Get-SidecarPath {
    param([string]$OutputPath)
    $dir  = Split-Path $OutputPath -Parent
    $base = [System.IO.Path]::GetFileNameWithoutExtension($OutputPath)
    return (Join-Path $dir ($base + ".pipeline.json"))
}

# Atomic write with retry. The temp-then-Replace dance:
#   1. Write payload to <sidecarDir>\.<name>.json.<id>.tmp
#   2. If the target sidecar exists, [File]::Replace swaps it in atomically
#      and routes the previous contents into <name>.json.<id>.backup, which
#      we then delete.
#   3. If the target doesn't exist yet, plain Move-Item -Force is sufficient.
#   4. Read back, verify pipeline_version round-tripped — guards against
#      silent corruption (truncated SMB writes, AV interception).
#
# FIX#11: Returns $true / $false. The pre-fix version returned void and
# silently swallowed errors; a sidecar-write failure then left the output
# on the outsource WITHOUT a sidecar, and the next run treated it as a
# legacy file and re-encoded forever. Callers MUST check the return value.
function Test-SidecarRoundTripValid {
    param(
        [Parameter(Mandatory)] $RoundTrip,
        [Parameter(Mandatory)] $Payload
    )

    $requiredText = @(
        'schema_version',
        'pipeline_version',
        'route',
        'output_file',
        'output_path',
        'publish_state',
        'publish_transaction_id'
    )
    foreach ($key in $requiredText) {
        $value = $RoundTrip.PSObject.Properties[$key].Value
        if ([string]::IsNullOrWhiteSpace([string]$value)) {
            return [pscustomobject]@{ Ok = $false; Reason = "$key missing" }
        }
    }

    if ([string]$RoundTrip.schema_version -ne 'pipeline_sidecar.v1') {
        return [pscustomobject]@{ Ok = $false; Reason = 'schema_version mismatch' }
    }
    if ([string]$RoundTrip.pipeline_version -ne [string]$Payload['pipeline_version']) {
        return [pscustomobject]@{ Ok = $false; Reason = 'pipeline_version mismatch' }
    }
    if ([string]$RoundTrip.output_path -ne [string]$Payload['output_path']) {
        return [pscustomobject]@{ Ok = $false; Reason = 'output_path mismatch' }
    }
    if ([string]$RoundTrip.publish_transaction_id -ne [string]$Payload['publish_transaction_id']) {
        return [pscustomobject]@{ Ok = $false; Reason = 'publish_transaction_id mismatch' }
    }
    $payloadSourceV2 = [string]$Payload['source_identity_v2']
    if (-not [string]::IsNullOrWhiteSpace($payloadSourceV2) -and [string]$RoundTrip.source_identity_v2 -ne $payloadSourceV2) {
        return [pscustomobject]@{ Ok = $false; Reason = 'source_identity_v2 mismatch' }
    }
    $payloadSourceV1 = [string]$Payload['source_identity']
    if ([string]::IsNullOrWhiteSpace($payloadSourceV2) -and -not [string]::IsNullOrWhiteSpace($payloadSourceV1) -and [string]$RoundTrip.source_identity -ne $payloadSourceV1) {
        return [pscustomobject]@{ Ok = $false; Reason = 'source_identity mismatch' }
    }
    if ($null -eq $RoundTrip.PSObject.Properties['output_size'].Value) {
        return [pscustomobject]@{ Ok = $false; Reason = 'output_size missing' }
    }
    # S2 — also compare the round-tripped value against the payload. The
    # previous check only asserted presence, so a truncated SMB write
    # that landed `"output_size": 0` would pass validation; then
    # Test-OutputNeedsReprocess would detect the disk-size mismatch every
    # run and re-encode the file forever. Catches silent corruption from
    # interrupted Replace, antivirus interception, or partial flushes.
    $payloadSize = $Payload['output_size']
    if ($null -ne $payloadSize) {
        $payloadLong = $null
        $roundTripLong = $null
        try { $payloadLong = [long]$payloadSize } catch {}
        try { $roundTripLong = [long]$RoundTrip.output_size } catch {}
        if ($null -ne $payloadLong -and $null -ne $roundTripLong -and $payloadLong -ne $roundTripLong) {
            return [pscustomobject]@{ Ok = $false; Reason = "output_size mismatch (payload=$payloadLong, round-trip=$roundTripLong)" }
        }
    }

    $requiredArrays = @(
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

function Move-SidecarTempIntoPlace {
    param(
        [Parameter(Mandatory)] [string] $TempPath,
        [Parameter(Mandatory)] [string] $DestinationPath
    )

    # PowerShell 7 runs on .NET with File.Move(source, dest, overwrite).
    # This keeps the fallback on a same-directory overwrite path instead of
    # explicitly deleting the old sidecar before the new one is visible.
    [System.IO.File]::Move($TempPath, $DestinationPath, $true)
}

function Write-Sidecar {
    param(
        [string]$OutputPath,
        [string]$Route,           # "remux" | "encode" | "encode-cpu-fallback"
        [object]$Extra = @{},
        [int]$MaxRetries = 3,
        [switch]$SkipCompletedManifest
    )
    $sidecar = Get-SidecarPath $OutputPath
    $createdAt = (Get-Date -Format 'o')
    $payload = [ordered]@{
        schema_version   = 'pipeline_sidecar.v1'
        product_version  = if ($script:ProductVersion) { [string]$script:ProductVersion } else { '' }
        pipeline_version = $script:PipelineVersion
        created_at       = $createdAt
        encoded_at       = $createdAt
        job_id           = if ($script:CurrentJobId) { [string]$script:CurrentJobId } else { '' }
        correlation_id   = if ($script:PipelineRunId) { [string]$script:PipelineRunId } else { '' }
        route            = $Route
        output_file      = Split-Path $OutputPath -Leaf
    }
    foreach ($k in $Extra.Keys) { $payload[$k] = $Extra[$k] }
    foreach ($requiredArray in @('tx3g_srt_tracks', 'tx3g_srt_failures', 'bdpgs_srt_failures', 'vobsub_srt_failures', 'tx3g_embedded_srt_tracks', 'bdpgs_embedded_srt_tracks', 'vobsub_embedded_srt_tracks')) {
        if (-not $payload.Contains($requiredArray)) { $payload[$requiredArray] = @() }
    }
    # S1 — Depth 5 was silently truncating route_plan.decision_trace[].data,
    # source_media_profile, folder_policy, audio/subtitle decisions, and
    # encode_selected_attempt.encode_ladder_profile to "@{...}" / "System.
    # Collections.Hashtable" strings on the disk sidecar. Bump to 10 to cover
    # every nesting level the pipeline currently produces with headroom.
    $json = $payload | ConvertTo-Json -Depth 10

    # S5 — Some SMB / FAT32 / NFS-on-Windows shares don't fully support
    # System.IO.File.Replace's transactional semantics and throw
    # IOException on the first attempt; retrying the same Replace fails
    # the same way. Track whether Replace ever fails on this sidecar
    # path and switch to an overwrite-move fallback on the retry.
    $skipReplace = $false
    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        $tmp = $null
        $backup = $null
        try {
            $sidecarDir = Split-Path $sidecar -Parent
            if (-not (Test-Path -LiteralPath $sidecarDir)) {
                New-Item -ItemType Directory -Path $sidecarDir -Force | Out-Null
            }
            $id = [guid]::NewGuid().ToString("N")
            $tmp = Join-Path $sidecarDir ("." + (Split-Path $sidecar -Leaf) + ".$id.tmp")
            $backup = Join-Path $sidecarDir ("." + (Split-Path $sidecar -Leaf) + ".$id.backup")
            [System.IO.File]::WriteAllText($tmp, $json, [System.Text.UTF8Encoding]::new($false))
            if (Test-Path -LiteralPath $sidecar) {
                if ($skipReplace) {
                    # Volume rejected Replace last attempt. Fall back to
                    # same-directory overwrite move. It is not as strong
                    # as File.Replace's backup semantics, but it avoids the
                    # explicit delete gap where concurrent readers could see
                    # no sidecar at all.
                    Move-SidecarTempIntoPlace -TempPath $tmp -DestinationPath $sidecar
                } else {
                    try {
                        [System.IO.File]::Replace($tmp, $sidecar, $backup, $true)
                        Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
                    } catch {
                        # Catch the specific "Replace not supported on
                        # this volume" / cross-device failures and arm
                        # the fallback for the next retry.
                        $skipReplace = $true
                        Write-Log "Sidecar write: [System.IO.File]::Replace failed on '$sidecar' (will use overwrite move on retry): $($_.Exception.Message)" "WARN"
                        throw
                    }
                }
            } else {
                Move-Item -LiteralPath $tmp -Destination $sidecar -Force -ErrorAction Stop
            }
            $roundTrip = Get-Content -LiteralPath $sidecar -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
            $validation = Test-SidecarRoundTripValid -RoundTrip $roundTrip -Payload $payload
            if (-not $validation.Ok) {
                throw "sidecar validation failed after write: $($validation.Reason)"
            }
            # Mirror this completion into the local completed-jobs manifest.
            # Failure to append is non-fatal — the sidecar on the outsource
            # remains the source of truth. The manifest is a read-optimized
            # local cache for the desktop UI.
            if (-not $SkipCompletedManifest) {
                Add-CompletedJobsManifestEntry -OutputPath $OutputPath -Payload $payload
            }
            return $true
        } catch {
            Write-Log "Sidecar write failed (attempt $attempt/$MaxRetries) for $OutputPath : $_" "WARN"
            if ($tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
            if ($backup) { Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue }
            if ($attempt -lt $MaxRetries) { if (-not (Start-StopAwareSleep 2)) { break } }
        }
    }
    Write-Log "Sidecar write FAILED permanently for $OutputPath" "ERROR"
    return $false
}

# Append one JSON line to the local completed-jobs manifest. Best-effort:
# any failure is logged and swallowed because the outsource-side sidecar is
# the source of truth and manifest-write failure must not abort the pipeline.
# Safe against concurrent writers because pipeline runs are serialized by
# the Global\MediaPipelineSingleInstance mutex.
function Add-CompletedJobsManifestEntry {
    param(
        [Parameter(Mandatory)] [string]$OutputPath,
        [Parameter(Mandatory)] $Payload
    )
    try {
        if (-not (Test-Path -LiteralPath $LocalCompleted)) {
            New-Item -ItemType Directory -Path $LocalCompleted -Force | Out-Null
        }
        # Clone the sidecar payload and add fields the UI needs to show the
        # entry without ever opening a remote file: absolute output path and
        # a logged-at timestamp (distinct from encoded_at, which may be an
        # older parked-push timestamp).
        $entry = [ordered]@{}
        foreach ($k in $Payload.Keys) { $entry[$k] = $Payload[$k] }
        if (-not $entry.Contains('schema_version')) { $entry['schema_version'] = 'completed_job.v1' }
        if (-not $entry.Contains('output_path')) { $entry['output_path'] = $OutputPath }
        if (-not $entry.Contains('job_id')) { $entry['job_id'] = if ($script:CurrentJobId) { [string]$script:CurrentJobId } else { '' } }
        if (-not $entry.Contains('correlation_id')) { $entry['correlation_id'] = if ($script:PipelineRunId) { [string]$script:PipelineRunId } else { '' } }
        $loggedAt = (Get-Date -Format 'o')
        $entry['logged_at'] = $loggedAt
        if (-not $entry.Contains('created_at')) { $entry['created_at'] = $loggedAt }
        # S1 — match the sidecar's depth so the manifest mirror doesn't
        # truncate fields that the disk sidecar already preserves.
        Write-JsonLineAppend -Path $CompletedJobsManifest -Payload $entry -Depth 10 | Out-Null
    } catch {
        Write-Log "Completed-jobs manifest append failed for $OutputPath : $_" "WARN"
    }
}

function Add-CompletedJobsManifestEntryFromSidecar {
    param([Parameter(Mandatory)] [string] $OutputPath)
    $sidecar = Get-SidecarPath $OutputPath
    try {
        if (-not (Test-Path -LiteralPath $sidecar -PathType Leaf)) {
            Write-Log "Completed-jobs manifest append skipped; sidecar missing for $OutputPath" "WARN"
            return $false
        }
        $json = Get-Content -LiteralPath $sidecar -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $payload = [ordered]@{}
        foreach ($prop in @($json.PSObject.Properties)) {
            $payload[$prop.Name] = $prop.Value
        }
        Add-CompletedJobsManifestEntry -OutputPath $OutputPath -Payload $payload
        return $true
    } catch {
        Write-Log "Completed-jobs manifest append from sidecar failed for $OutputPath : $_" "WARN"
        return $false
    }
}

# Read sidecar (if present) and decide whether the existing output is stale
# relative to $MinPipelineVersion. Returns $true when the file should be
# reprocessed. When no sidecar exists, returns $true (legacy output).
#
# When $SourceFile is provided, also compares source identity:
#   - source size (cheapest filter, catches truncations / replacements)
#   - source_identity_v2 (preferred — sample-hash-based)
#   - source_identity (legacy fallback — path/size/mtime)
# A match on either v2 or v1 (where v1 is allowed for legacy v2 algorithms)
# returns FALSE (no reprocess). Mismatches return TRUE.
function Test-OutputNeedsReprocess {
    param(
        [string]$OutputPath,
        $SourceFile = $null
    )
    if ($script:ReprocessAll) {
        Write-Log "REPROCESS: ReprocessAll=true — forcing reprocess of $(Split-Path $OutputPath -Leaf)" "DEBUG"
        return $true
    }
    $sidecar = Get-SidecarPath $OutputPath
    if (-not (Test-Path -LiteralPath $sidecar)) {
        Write-Log "REPROCESS: no sidecar for $(Split-Path $OutputPath -Leaf) — treating as legacy" "DEBUG"
        return $true
    }
    try {
        $json = Get-Content -LiteralPath $sidecar -Raw | ConvertFrom-Json
        $sidecarVer = [string]$json.pipeline_version
        if (-not $sidecarVer) { return $true }
        if (Compare-PipelineVersion $sidecarVer $script:MinPipelineVersion) {
            Write-Log ("REPROCESS: sidecar version {0} < min {1} for {2}" `
                -f $sidecarVer, $script:MinPipelineVersion, (Split-Path $OutputPath -Leaf)) "DEBUG"
            return $true
        }

        # Output-size sanity check (v1.0-review item #7). A truncated or
        # replaced output on disk would otherwise sail through the identity
        # checks below — those compare the SOURCE, not the output. We only
        # enforce this when the sidecar actually recorded an output_size
        # (legacy sidecars predating that field skip the check, preserving
        # backward compatibility — a missing output_size is treated as
        # "unknown", not "zero").
        $sidecarOutputSize = $null
        if ($null -ne $json.output_size -and "$($json.output_size)" -match '^\d+$') {
            $sidecarOutputSize = [long]$json.output_size
        }
        if ($null -ne $sidecarOutputSize) {
            try {
                $diskSize = [long](Get-Item -LiteralPath $OutputPath -ErrorAction Stop).Length
                if ($diskSize -ne $sidecarOutputSize) {
                    Write-Log ("REPROCESS: output size on disk does not match sidecar for {0} ({1} -> {2})" -f `
                        (Split-Path $OutputPath -Leaf), $sidecarOutputSize, $diskSize) "WARN"
                    return $true
                }
            } catch {
                # Get-Item failed (file vanished between Test-Path and now,
                # share dropped, etc). Treat as "needs reprocess" rather
                # than silently keeping a sidecar pointing at a missing
                # file — the upstream caller's Test-Path check is racy
                # against share connectivity.
                Write-Log "REPROCESS: could not stat output to verify size: $_" "WARN"
                return $true
            }
        }

        if ($SourceFile) {
            $sidecarSourceSize = $null
            if ($null -ne $json.source_size -and "$($json.source_size)" -match '^\d+$') {
                $sidecarSourceSize = [long]$json.source_size
            }
            if ($null -ne $sidecarSourceSize -and $sidecarSourceSize -ne [long]$SourceFile.Length) {
                Write-Log ("REPROCESS: source size changed for {0} ({1} -> {2})" -f `
                    (Split-Path $OutputPath -Leaf), $sidecarSourceSize, [long]$SourceFile.Length) "WARN"
                return $true
            }

            $sidecarSourceV2 = [string]$json.source_identity_v2
            $sidecarSource = [string]$json.source_identity
            $currentSourceV2 = $null
            $currentSource = $null
            if (-not [string]::IsNullOrWhiteSpace($sidecarSourceV2)) {
                $currentSourceV2 = Get-SourceIdentityKeyV2 $SourceFile
                if ($currentSourceV2 -eq $sidecarSourceV2) {
                    return $false
                }

                $sidecarSourceV2Algorithm = [string]$json.source_identity_v2_algorithm
                # Only sidecars that explicitly identify an old v2 algorithm
                # may fall back to the weaker path/size/mtime identity. Missing
                # algorithm metadata means the recorded v2 is authoritative.
                if ((Test-LegacySourceIdentityV2Algorithm $sidecarSourceV2Algorithm) -and
                    -not [string]::IsNullOrWhiteSpace($sidecarSource)) {
                    $currentSource = Get-SourceIdentityKey $SourceFile
                    if ($currentSource -eq $sidecarSource) {
                        Write-Log ("REPROCESS: source_identity_v2 mismatch ignored for legacy v2 algorithm '{0}' on {1}" -f `
                            $sidecarSourceV2Algorithm, (Split-Path $OutputPath -Leaf)) "WARN"
                        return $false
                    }
                }

                Write-Log "REPROCESS: source identity v2 changed for $(Split-Path $OutputPath -Leaf)" "WARN"
                return $true
            }

            if (-not [string]::IsNullOrWhiteSpace($sidecarSource)) {
                $currentSource = Get-SourceIdentityKey $SourceFile
                if ($currentSource -ne $sidecarSource) {
                    Write-Log "REPROCESS: source identity changed for $(Split-Path $OutputPath -Leaf)" "WARN"
                    return $true
                }
            } else {
                Write-Log "REPROCESS: sidecar lacks source identity for $(Split-Path $OutputPath -Leaf)" "WARN"
                return $true
            }
        }
        return $false
    } catch {
        Write-Log "Sidecar read failed ($_) — reprocessing" "DEBUG"
        return $true
    }
}
