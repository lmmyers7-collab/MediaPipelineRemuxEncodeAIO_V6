---
file: engine/queue/file_overrides.ps1
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-05-29
last_reviewed: 2026-05-29
sha256: 7fe71c42beef93f168aa8c4925f15da317c02683244312a42a030f205079ef21
---
# `engine/queue/file_overrides.ps1`

**Purpose:** Load file_overrides.json from the state root.

**Functions:** `Get-AudioTrackTitleOverride`, `Get-FileOverrideAudioSettings`, `Get-FileOverrideSubtitleSettings`, `Get-FileOverridesManifest`, `Get-SubtitleTrackTitleOverride`, `Merge-FileOverrideIntoActiveOverrides`, `Resolve-FileOverride`, `Test-AudioTrackKeptByOverride`, `Test-SubtitleTrackKeptByOverride`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/queue/file_overrides.ps1`._
