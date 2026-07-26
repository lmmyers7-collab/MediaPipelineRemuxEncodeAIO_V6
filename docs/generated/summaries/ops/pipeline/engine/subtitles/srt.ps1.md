---
file: ops/pipeline/engine/subtitles/srt.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: subtitles
token_priority: high
owner_domain: subtitles
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 0daff0f49c8f37c7d06d4b010aa09b0b8a9fa31476f3ca27ccf07ac704c790e6
---
# `ops/pipeline/engine/subtitles/srt.ps1`

**Purpose:** PowerShell implementation for srt; exposes Complete-AtomicSrtWrite, Convert-SrtTimestampToMilliseconds, Copy-SrtAtomic.

**Public symbols:** `Complete-AtomicSrtWrite`, `Convert-SrtTimestampToMilliseconds`, `Copy-SrtAtomic`, `Merge-AdjacentIdenticalCues`, `Move-SrtTempIntoPlace`, `New-SrtAtomicTempPath`, `Test-SrtFileUsable`
**Invoked tools:** `pgstosrt`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/subtitles/srt.ps1`._
