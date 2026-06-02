---
file: Pipeline/Audit-MediaLibrary.ps1
pipeline_stage: observability
token_priority: medium
owner_domain: audit
last_modified: 2026-06-01
last_reviewed: 2026-05-30
sha256: 87ffe628a0887b637a8eb63f3927acd5d1dee438a2cbd8d9e9c80694ecaa9a13
---
# `Pipeline/Audit-MediaLibrary.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Add-AuditIssue`, `Add-AuditSubtitleCompatibilityIssues`, `Analyze-Sidecar`, `Format-AudioCandidateLabel`, `Get-AudioCodecFidelityRank`, `Get-AudioStreamFidelityScore`, `Get-AuditNormalizedPathKey`, `Get-AuditResultForFile`, `Get-AuditSidecarSrtRecordPath`, `Get-AuditTx3gGenericSrtSuffixes`, `Get-AuditValidatedEmbeddedSrtRecordCount`, `Get-CompletedAuditTaskText`, `Get-DefaultStream`, `Get-ExpectedDefaultAudioCandidate`, `Get-LibraryLookupTitle`, `Get-MatchingExternalSrtFilesForAudit`, `Get-NormalizedPreferredAudioLanguages`, `Get-StreamDispositionValue`, `Get-StreamTagValue`, `Get-TVParseRenameSuggestion`, `Get-TagValue`, `Invoke-AuditNativeCommand`, `New-AuditResult`, `Normalize-AudioLanguagePreferenceValue`, `Normalize-LibraryLookupText`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths Pipeline/Audit-MediaLibrary.ps1`._
