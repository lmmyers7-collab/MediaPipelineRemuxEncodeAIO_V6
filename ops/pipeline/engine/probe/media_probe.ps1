# ==============================================================================
# ops\pipeline\engine\probe\media_probe.ps1
# ==============================================================================
# ffprobe-driven media inspection helpers used by ops/pipeline/engine/probe/stage.ps1 and
# the legacy media-probe shim.
#
# Dot-sourced from the main script. Reads the following at call time:
#
#   $ffprobePath              — resolved at startup (Resolve-BundledExecutable)
#   $EnableIntegrityCheck     — config (Test-FileIntegrityDetailed gate)
#   $SkipStabilityCheck       — config (Test-FileStable gate)
#   $FileStabilityWait        — config (per-interval seconds)
#   Invoke-NativeCommand      — ops\pipeline\engine\shared\native.ps1
#   Start-StopAwareSleep      — ops\pipeline\engine\shared\native.ps1
#   Get-FFprobeFailureCode    — ops\pipeline\engine\shared\failure_codes.ps1
#   Write-Log                 — Modules\Logging.ps1
#
# Two functional groups live here:
#
#   Single-shot probes that return a scalar (codec name / lang / HDR flag /
#   duration). Each runs ffprobe with a 30 s timeout and degrades to a
#   sentinel value ("unknown" / "und" / 0.0 / $false) on failure rather
#   than throwing.
#
#   File-level integrity & stability tests used as gates before processing
#   a source file or accepting an output:
#     - Test-FileStable        — three-sample size check on the source
#     - Test-FileIntegrity*    — ffprobe-based "can we read this?" probe
#     - Test-DurationMatch     — post-encode "is the output the right length?"
#                                with the -AllowAVFallback heuristic for
#                                ASS-subtitle-tail container differences
#
#   Output logging used after processing or publish:
#     - Write-OutputSummary           — one-line final output stream summary
#     - Write-PlexCompatibilityReport — Plex/direct-play compatibility outlook
# ==============================================================================

# Constructor for the integrity-result pscustomobject. Every
# Test-FileIntegrityDetailed exit point routes through this so the schema
# (and the default ErrorCode of 'OK'/'MEDIA_INTEGRITY_FAILED') stays
# consistent. Failure-code callers downstream rely on the ErrorCode field.
. (Join-Path $PSScriptRoot 'media_probe_integrity.ps1')
. (Join-Path $PSScriptRoot 'media_probe_streams.ps1')
. (Join-Path $PSScriptRoot 'media_probe_hdr.ps1')
. (Join-Path $PSScriptRoot 'media_probe_reports.ps1')



# Detailed source-integrity probe used for failure classification. Returns a
# rich result object (see New-FileIntegrityResult). Callers that only want
# a yes/no answer should use Test-FileIntegrity instead.


# Convenience wrapper for callers that only want a Boolean.


# Three-sample size check. Returns $true only when three Get-Item.Length
# reads spaced FileStabilityWait/2 seconds apart all match. Two-sample
# would catch most mid-write cases but bursty network shares can produce
# false-stable readings; the third sample mostly eliminates that.
# Returns $false on stop-flag interrupt as well as on actual size churn.


# ============================================================================
# SCALAR PROBES — each returns a single value, sentinel on failure
# ============================================================================

# Returns the source's container-level title tag (format.tags.title) trimmed,
# or '' when absent / probe-failure. Plex and other library managers fall
# back to this title when filename parsing is ambiguous, so the remux path
# uses it to seed mkvmerge --title instead of always overwriting with the
# generic "Encoded by MediaPipeline ..." string.  R8 fix.


# Returns the v:0 codec name lower-cased ('hevc', 'h264', 'av1', 'mpeg2video',
# 'vc1', etc.) or 'unknown' on probe failure. Used to decide remux vs encode.






















# Returns the language tag of the audio stream marked default, falling back
# to the first audio stream, then to "und". Lower-cased ISO-639-2/B code.
#
# Defensive notes (post-extraction fix; addresses v1.0-review item #11):
#
#   1. `$json.streams` is array-wrapped via @(...) so single-stream JSON
#      doesn't unwrap to a bare PSCustomObject — `[0]` indexing on a
#      non-array PSCustomObject silently returns $null in PS7.
#
#   2. Newer ffprobe builds OMIT the `disposition` node from JSON output
#      when no flags are set on the stream. The previous code wrote
#      `$s.disposition.default -eq 1` which is fine when disposition is
#      missing (dereferencing $null returns $null, $null -eq 1 is $false),
#      but the surrounding logic could silently drop into the catch block
#      via the `return if (...) {...} else {...}` chain when the .Trim()
#      cast failed on a PSCustomObject deserialization quirk.
#
#   3. tags.language is now explicitly [string]-cast before .ToLower() so
#      a PSCustomObject value (which can happen with malformed nested
#      tags) doesn't NoMethod-throw into the catch.


# Cheap HDR detection by color_transfer. Only PQ (smpte2084) and HLG
# (arib-std-b67) are recognized -- that covers all HDR10/HDR10+/HLG content.
# Dolby Vision metadata is layered on top of one of those transfers, so it's
# implicitly handled. Probe failures are explicit so encode routing does not
# silently flatten unknown HDR content through the SDR profile.






















# ============================================================================
# DURATION HELPERS
# ============================================================================

# Container duration in seconds. Returns 0.0 on probe failure or unparseable
# output — callers use 0.0 as the sentinel for "could not determine".


# Last-packet pts_time across the primary video and audio streams. Used as a
# fallback in Test-DurationMatch when the container duration disagrees: an
# ASS subtitle cue extending past actual A/V end inflates the container
# duration even though the encoded A/V is identical end-to-end. Returns 0.0
# when neither v:0 nor a:0 produced parseable packet timestamps.
#
# Default 180s timeout is generous because packet enumeration is O(file
# length) — for 4K films the probe can take 30-60s.


# Post-encode duration sanity check. Catches silent truncations where ffmpeg
# exits 0 but the output is shorter than the source.
#
# Source-probe-failure policy: returns $false. Publish verification cannot
# accept an output when the source duration cannot be measured. Output-probe-
# failure policy: returns $false (the output is unreadable — treat as corrupt).
#
# -AllowAVFallback (used by encode/remux paths but not by integrity checks):
# when the container durations disagree by more than -ToleranceSeconds, fall
# back to comparing primary-A/V end times (Get-PrimaryAVEndTime). This
# tolerates the common case where a stray subtitle cue at the end of an ASS
# track inflates the source container duration; the encoded output is
# correct but Test-DurationMatch would otherwise reject it.


# ==============================================================================
# OUTPUT SUMMARY — one-line description of the final MKV's tracks
# ==============================================================================

# Probes $FilePath and writes one INFO log line summarising its streams.
# Format:
#   OUTPUT: 1.23GB | HEVC 1080p | JPN 2.0 FLAC, ENG 2.0 FLAC [def] | ENG ASS, ENG SRT [def], ENG ASS [signs]
