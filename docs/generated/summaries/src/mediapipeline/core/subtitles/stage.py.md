---
file: src/mediapipeline/core/subtitles/stage.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: subtitles
token_priority: high
owner_domain: subtitles
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 0535244592cba9c23b960f7bfc1eb998f4600aa2eedf6542ffdee70b28a7e137
---
# `src/mediapipeline/core/subtitles/stage.py`

**Purpose:** Scratch-only Python executor for standalone ASS/SSA to SRT conversion.

**Public symbols:** `execute_scratch_subtitle_stage`, `SubtitleStageBoundaryError`, `SubtitleStageFingerprintError`, `SubtitleStageRecoveryError`
**In-repo imports:** `mediapipeline.contracts.stage_mutation`, `mediapipeline.core.paths.layout`, `mediapipeline.pipeline.ass_to_srt.ass_events`, `mediapipeline.pipeline.ass_to_srt.srt`, `mediapipeline.pipeline.ass_to_srt.styles`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/subtitles/stage.py`._
