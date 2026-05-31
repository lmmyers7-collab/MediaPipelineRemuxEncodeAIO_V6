---
file: Pipeline/Tests/Unit/Invoke-VobSubSubtitleChecks.ps1
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-05-31
last_reviewed: 2026-05-31
sha256: b48cee39ed2f1b123faedded113a4d48772702aef4341d3a0adb60072aea17e9
---
# `Pipeline/Tests/Unit/Invoke-VobSubSubtitleChecks.ps1`

**Purpose:** Focused PowerShell unit checks for VobSub subtitle detection, language fallback, sidecar pair handling, fake OCR success, and missing IDX/SUB failure records.

**Functions:** `Assert-Equal`, `Assert-True`, `Complete-AtomicSrtWrite`, `Get-ErrorTextSummary`, `Get-NormalizedSubtitleLanguage`, `Get-SubtitleOperationTimeoutSeconds`, `Invoke-VobSubOcrCommand`, `New-StandardFailureRecord`, `New-SrtAtomicTempPath`, `Test-SrtFileUsable`, `Write-Log`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths Pipeline/Tests/Unit/Invoke-VobSubSubtitleChecks.ps1`._
