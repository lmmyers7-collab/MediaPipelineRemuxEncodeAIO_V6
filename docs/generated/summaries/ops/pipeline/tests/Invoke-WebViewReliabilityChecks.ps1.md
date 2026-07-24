---
file: ops/pipeline/tests/Invoke-WebViewReliabilityChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-23
last_reviewed: 2026-06-04
sha256: 9f5caecc8c8b5e3d0418fceb29b3c2d8fd41afce71b22aa8353ad4c5cb490d69
---
# `ops/pipeline/tests/Invoke-WebViewReliabilityChecks.ps1`

**Purpose:** PowerShell implementation for invoke web view reliability checks; exposes Assert-Absent, Assert-Container, Assert-Leaf.

**Public symbols:** `Assert-Absent`, `Assert-Container`, `Assert-Leaf`, `Assert-TreeNotMatch`, `Assert-True`, `Read-Text`, `Test-PowerShellParse`
**HTTP routes:** `/api/backend/shutdown`, `/api/pending-publish/recovery-plan`, `/api/pipeline/control`, `/api/pipeline/start`, `/api/rename/apply`, `/api/rename/preview`, `/api/sample-validation/append`, `/api/schedule/preview`, `/api/schedule/save`, `/api/settings/preview-patch`, `/api/settings/save-patch`
**Invoked tools:** `ffmpeg`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Invoke-WebViewReliabilityChecks.ps1`._
