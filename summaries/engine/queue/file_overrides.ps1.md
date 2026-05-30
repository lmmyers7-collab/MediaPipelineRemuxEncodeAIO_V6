---
file: engine/queue/file_overrides.ps1
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-05-29
last_reviewed: 2026-05-29
sha256: e8a43d7e5e10381508d7967306bd3e5afb3eb4b220be0d4fda672cac60c041af
---
# `engine/queue/file_overrides.ps1`

**Purpose:** Load file_overrides.json from the state root.

**Functions:** `Get-AudioTrackTitleOverride`, `Get-FileOverrideAudioSettings`, `Get-FileOverrideSubtitleSettings`, `Get-FileOverridesManifest`, `Get-SubtitleTrackTitleOverride`, `Merge-FileOverrideIntoActiveOverrides`, `Resolve-FileOverride`, `Test-AudioTrackKeptByOverride`, `Test-SubtitleTrackKeptByOverride`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/queue/file_overrides.ps1`._
