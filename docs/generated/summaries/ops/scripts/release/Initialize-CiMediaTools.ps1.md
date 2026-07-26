---
file: ops/scripts/release/Initialize-CiMediaTools.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-12
last_reviewed: 2026-06-28
sha256: 5a6618e410572b889a435bda2325b8a2668b48855f273c008bb6b1f53e8a8a5d
---
# `ops/scripts/release/Initialize-CiMediaTools.ps1`

**Purpose:** PowerShell implementation for initialize ci media tools; exposes Assert-FileSha256, Copy-DirectoryContents, Find-ExecutableInRoots.

**Public symbols:** `Assert-FileSha256`, `Copy-DirectoryContents`, `Find-ExecutableInRoots`, `Get-ToolRoots`, `Install-MissingPackages`, `Install-PgsToSrtRuntime`, `Invoke-CheckedCommand`, `Invoke-VerifiedDownload`, `Resolve-CommandSource`, `Resolve-Executable`, `Resolve-ProvisionSource`, `Resolve-RepoRoot`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`, `pgstosrt`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/scripts/release/Initialize-CiMediaTools.ps1`._
