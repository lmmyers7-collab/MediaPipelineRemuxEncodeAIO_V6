---
file: engine/audit/policy.ps1
pipeline_stage: observability
token_priority: medium
owner_domain: audit
last_modified: 2026-06-03
last_reviewed: 2026-05-29
sha256: 4ab01b5d47555680e572f6f0fa89f3a90fce7121dfdaaf8936314eec22bc683c
---
# `engine/audit/policy.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Convert-ToLowerInvariantSafe`, `ConvertTo-AuditIgnoreKey`, `ConvertTo-AuditIssueCodeWeightMap`, `ConvertTo-AuditScorePolicy`, `ConvertTo-AuditScoreValue`, `Get-AuditIgnoreEntry`, `Get-AuditKnownIssueCodeGroups`, `Get-AuditPolicyProperty`, `Get-AuditScorePolicyIssueCodeWeight`, `Get-AuditScorePolicyValue`, `Get-BucketRank`, `Get-DefaultAuditScorePolicy`, `Get-EffectiveIssues`, `Get-IssueEffectiveBucket`, `Get-IssuePriorityWeight`, `Get-NonSidecarIssues`, `Get-PrimaryIssue`, `Get-PriorityFixLevel`, `Get-PriorityLevelRank`, `Get-PriorityScore`, `Import-AuditIgnoreManifest`, `Import-AuditScorePolicy`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/audit/policy.ps1`._
