---
file: src/mediapipeline/pipeline/ass_to_srt_cli.py
pipeline_stage: subtitles
token_priority: high
owner_domain: subtitles
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: d637fceafcf709eda06731508e231d722778256b3f9dbdb929747a5b022c1df7
---
# `src/mediapipeline/pipeline/ass_to_srt_cli.py`

**Purpose:** ass_to_srt.py  —  Convert one ASS subtitle stream from an MKV to plain SRT.

**Classes:** `ChildProcessGuard`
**Public functions:** `atomic_write_json()`, `atomic_write_text()`, `fail_with_summary()`, `load_ass_with_best_encoding()`, `main()`, `parse_args()`, `run_ffmpeg_extract()`, `write_summary_json()`
**In-repo imports:** `mediapipeline.pipeline.ass_to_srt.ass_events`, `mediapipeline.pipeline.ass_to_srt.log`, `mediapipeline.pipeline.ass_to_srt.srt`, `mediapipeline.pipeline.ass_to_srt.styles`, `mediapipeline.pipeline.ass_to_srt.text`, `mediapipeline.pipeline.ass_to_srt.timing`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/pipeline/ass_to_srt_cli.py`._
