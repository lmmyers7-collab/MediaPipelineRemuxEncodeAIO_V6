---
file: ops/pipeline/entrypoints/Audit-MediaLibrary.ps1
pipeline_stage: observability
token_priority: medium
owner_domain: audit
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: b3474980cb53a2e04d1ae9f0ea44674d1456b9efb4f31c67a3bdf13fc4ba03e9
---
# `ops/pipeline/entrypoints/Audit-MediaLibrary.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Add-AuditIssue`, `Add-AuditSubtitleCompatibilityIssues`, `Analyze-Sidecar`, `Format-AudioCandidateLabel`, `Get-AudioCodecFidelityRank`, `Get-AudioStreamFidelityScore`, `Get-AuditNormalizedPathKey`, `Get-AuditResultForFile`, `Get-AuditSidecarSrtRecordPath`, `Get-AuditTx3gGenericSrtSuffixes`, `Get-AuditValidatedEmbeddedSrtRecordCount`, `Get-CompletedAuditTaskText`, `Get-DefaultStream`, `Get-ExpectedDefaultAudioCandidate`, `Get-LibraryLookupTitle`, `Get-MatchingExternalSrtFilesForAudit`, `Get-NormalizedPreferredAudioLanguages`, `Get-StreamDispositionValue`, `Get-StreamTagValue`, `Get-TVParseRenameSuggestion`, `Get-TagValue`, `Invoke-AuditNativeCommand`, `New-AuditResult`, `Normalize-AudioLanguagePreferenceValue`, `Normalize-LibraryLookupText`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/entrypoints/Audit-MediaLibrary.ps1`._
