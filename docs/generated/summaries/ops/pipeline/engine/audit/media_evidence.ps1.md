---
file: ops/pipeline/engine/audit/media_evidence.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: observability
token_priority: medium
owner_domain: audit
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 39a4d59304df657247b2320f7df7931463fb47d7b572cac1daffaa469a76fe23
---
# `ops/pipeline/engine/audit/media_evidence.ps1`

**Purpose:** PowerShell implementation for media evidence; exposes Add-AuditIssue, Format-AudioCandidateLabel, Get-AudioCodecFidelityRank.

**Public symbols:** `Add-AuditIssue`, `Format-AudioCandidateLabel`, `Get-AudioCodecFidelityRank`, `Get-AudioStreamFidelityScore`, `Get-AuditNormalizedPathKey`, `Get-AuditSidecarSrtRecordPath`, `Get-AuditTx3gGenericSrtSuffixes`, `Get-AuditValidatedEmbeddedSrtRecordCount`, `Get-DefaultStream`, `Get-ExpectedDefaultAudioCandidate`, `Get-MatchingExternalSrtFilesForAudit`, `Get-NormalizedPreferredAudioLanguages`, `Get-StreamDispositionValue`, `Get-StreamTagValue`, `Get-TagValue`, `New-AuditResult`, `Normalize-AudioLanguagePreferenceValue`, `Test-AudioTitleLooksLikeCommentary`, `Test-AuditBdpgsSubtitleStream`, `Test-AuditEmbeddedSrtRecordMatchesStream`, `Test-AuditSrtFileUsable`, `Test-AuditTx3gSidecarSrtRecordUsable`, `Test-AuditTx3gSubtitleStream`, `Test-AuditVobSubSubtitleStream`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/audit/media_evidence.ps1`._
