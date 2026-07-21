---
file: ops/pipeline/engine/audit/reports.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: observability
token_priority: medium
owner_domain: audit
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 67c93ee19d7485507c42bfddf59f2b33f9c546bb1dae29634672590c0109fbc3
---
# `ops/pipeline/engine/audit/reports.ps1`

**Purpose:** PowerShell implementation for reports; exposes Convert-ResultForSerialization, Export-CsvAtomic, Get-AuditCsvColumnNames.

**Public symbols:** `Convert-ResultForSerialization`, `Export-CsvAtomic`, `Get-AuditCsvColumnNames`, `New-AuditCsvRows`, `New-AuditReportModel`, `Write-AuditReportBundle`, `Write-TextReport`
**Invoked tools:** `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/audit/reports.ps1`._
