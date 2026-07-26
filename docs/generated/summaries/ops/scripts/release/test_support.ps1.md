---
file: ops/scripts/release/test_support.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-23
last_reviewed: 2026-07-11
sha256: 5fa49a8f13b953e9e8335101192397f8621ea4459127e5bd7949397dd9be6f45
---
# `ops/scripts/release/test_support.ps1`

**Purpose:** PowerShell implementation for test support; exposes Assert-ReleasePathAbsent, Assert-ReleasePathPresent, Assert-ReleasePatternAbsent.

**Public symbols:** `Assert-ReleasePathAbsent`, `Assert-ReleasePathPresent`, `Assert-ReleasePatternAbsent`, `ConvertTo-ReleaseBool`, `ConvertTo-ReleaseStringArray`, `Get-ObjectPropertyValue`, `Import-MediaPipelineReleasePolicy`, `Invoke-PythonModuleCheck`, `Invoke-PythonPytestStyleTests`, `Invoke-PythonUnittestDiscovery`, `Invoke-ReleaseScriptCheck`, `Invoke-ReleaseScriptProcess`, `Record-ReleaseGateSkip`, `Resolve-ReleasePowerShell`, `Test-PowerShellParse`, `Test-ReleaseMapContainsKey`, `Test-ReleaseStringArrayEquals`, `Write-Fail`, `Write-Ok`, `Write-Section`, `Write-Warn`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/scripts/release/test_support.ps1`._
