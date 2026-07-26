---
file: ops/pipeline/engine/verify/media_track_verification.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: verify
last_modified: 2026-07-16
last_reviewed: 2026-07-10
sha256: 6692887d3aceef9bca40a5b9a0136021b311b9fad3c86302e781769a0200a892
---
# `ops/pipeline/engine/verify/media_track_verification.ps1`

**Purpose:** PowerShell implementation for media track verification; exposes Add-MediaTrackVerificationMismatch, ConvertTo-MediaTrackVerificationBool, Get-MediaTrackOutputInventory.

**Public symbols:** `Add-MediaTrackVerificationMismatch`, `ConvertTo-MediaTrackVerificationBool`, `Get-MediaTrackOutputInventory`, `Get-MediaTrackVerificationFacet`, `Get-MediaTrackVerificationValue`, `Get-NormalizedMediaTrackVerificationCodec`, `New-MediaTrackOutputVerificationPlan`, `New-MediaTrackOutputVerificationPlanFromFfmpegSubtitleArgs`, `Test-MediaTrackOutputVerification`
**Invoked stages:** `media-track-output-verify`
**Invoked tools:** `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/verify/media_track_verification.ps1`._
