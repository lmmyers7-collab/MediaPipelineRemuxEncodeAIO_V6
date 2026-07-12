---
file: ops/pipeline/engine/audit/media_evidence.ps1
pipeline_stage: observability
token_priority: medium
owner_domain: audit
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 39a4d59304df657247b2320f7df7931463fb47d7b572cac1daffaa469a76fe23
---
# `ops/pipeline/engine/audit/media_evidence.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Add-AuditIssue`, `Format-AudioCandidateLabel`, `Get-AudioCodecFidelityRank`, `Get-AudioStreamFidelityScore`, `Get-AuditNormalizedPathKey`, `Get-AuditSidecarSrtRecordPath`, `Get-AuditTx3gGenericSrtSuffixes`, `Get-AuditValidatedEmbeddedSrtRecordCount`, `Get-DefaultStream`, `Get-ExpectedDefaultAudioCandidate`, `Get-MatchingExternalSrtFilesForAudit`, `Get-NormalizedPreferredAudioLanguages`, `Get-StreamDispositionValue`, `Get-StreamTagValue`, `Get-TagValue`, `New-AuditResult`, `Normalize-AudioLanguagePreferenceValue`, `Test-AudioTitleLooksLikeCommentary`, `Test-AuditBdpgsSubtitleStream`, `Test-AuditEmbeddedSrtRecordMatchesStream`, `Test-AuditSrtFileUsable`, `Test-AuditTx3gSidecarSrtRecordUsable`, `Test-AuditTx3gSubtitleStream`, `Test-AuditVobSubSubtitleStream`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/audit/media_evidence.ps1`._
