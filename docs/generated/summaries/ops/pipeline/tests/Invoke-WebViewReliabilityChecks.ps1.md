---
file: ops/pipeline/tests/Invoke-WebViewReliabilityChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-26
last_reviewed: 2026-06-04
sha256: 8b8864c84b3e4c1e4cb62670bd2d9c7d6dcbe530ad058a9ec0212bcc00df25a0
---
# `ops/pipeline/tests/Invoke-WebViewReliabilityChecks.ps1`

**Purpose:** PowerShell implementation for invoke web view reliability checks; exposes Assert-Absent, Assert-Container, Assert-Leaf.

**Public symbols:** `Assert-Absent`, `Assert-Container`, `Assert-Leaf`, `Assert-TreeNotMatch`, `Assert-True`, `Read-Text`, `Test-PowerShellParse`
**HTTP routes:** `/api/backend/shutdown`, `/api/pending-publish/recovery-plan`, `/api/pipeline/control`, `/api/pipeline/start`, `/api/rename/apply`, `/api/rename/preview`, `/api/sample-validation/append`, `/api/schedule/preview`, `/api/schedule/save`, `/api/settings/preview-patch`, `/api/settings/save-patch`
**Invoked tools:** `ffmpeg`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Invoke-WebViewReliabilityChecks.ps1`._
