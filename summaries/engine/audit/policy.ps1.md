---
file: engine/audit/policy.ps1
pipeline_stage: observability
token_priority: medium
owner_domain: audit
last_modified: 2026-06-03
last_reviewed: 2026-05-29
sha256: 349a3b29d6b79d4aa636318eddf3ef40c6fa222f5d6412e95f6da59a24267ff6
---
# `engine/audit/policy.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Convert-ToLowerInvariantSafe`, `ConvertTo-AuditIgnoreKey`, `ConvertTo-AuditScorePolicy`, `Get-AuditIgnoreEntry`, `Get-AuditScorePolicyValue`, `Get-BucketRank`, `Get-DefaultAuditScorePolicy`, `Get-EffectiveIssues`, `Get-IssueEffectiveBucket`, `Get-IssuePriorityWeight`, `Get-NonSidecarIssues`, `Get-PrimaryIssue`, `Get-PriorityFixLevel`, `Get-PriorityLevelRank`, `Get-PriorityScore`, `Import-AuditIgnoreManifest`, `Import-AuditScorePolicy`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/audit/policy.ps1`._
