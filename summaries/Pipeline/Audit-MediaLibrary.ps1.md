---
file: Pipeline/Audit-MediaLibrary.ps1
pipeline_stage: observability
token_priority: medium
owner_domain: audit
last_modified: 2026-06-03
last_reviewed: 2026-05-30
sha256: 9543ead2ce9206a3f00e99b20326bda23fb4c4003abcb3aae4c6701bd8643fa7
---
# `Pipeline/Audit-MediaLibrary.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Add-AuditIssue`, `Add-AuditSubtitleCompatibilityIssues`, `Analyze-Sidecar`, `Format-AudioCandidateLabel`, `Get-AudioCodecFidelityRank`, `Get-AudioStreamFidelityScore`, `Get-AuditNormalizedPathKey`, `Get-AuditResultForFile`, `Get-AuditSidecarSrtRecordPath`, `Get-AuditTx3gGenericSrtSuffixes`, `Get-AuditValidatedEmbeddedSrtRecordCount`, `Get-CompletedAuditTaskText`, `Get-DefaultStream`, `Get-ExpectedDefaultAudioCandidate`, `Get-LibraryLookupTitle`, `Get-MatchingExternalSrtFilesForAudit`, `Get-NormalizedPreferredAudioLanguages`, `Get-StreamDispositionValue`, `Get-StreamTagValue`, `Get-TVParseRenameSuggestion`, `Get-TagValue`, `Invoke-AuditNativeCommand`, `New-AuditResult`, `Normalize-AudioLanguagePreferenceValue`, `Normalize-LibraryLookupText`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths Pipeline/Audit-MediaLibrary.ps1`._
