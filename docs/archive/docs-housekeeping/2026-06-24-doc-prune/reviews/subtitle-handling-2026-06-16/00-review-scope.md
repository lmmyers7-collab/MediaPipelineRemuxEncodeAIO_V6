# Subtitle Handling Review Scope

Date: 2026-06-16

Repository scope: current MediaPipelineRemuxEncodeAIO workspace

Requested scope:

- ASS/SSA handling
- TX3G/mov_text handling
- BDPGS/PGS OCR handling
- VobSub/IDX/SUB OCR handling
- SRT creation, validation, and atomic writes
- Subtitle language filtering
- Preservation defaults
- Supplemental subtitle rules
- OCR tool path resolution
- Conversion failure handling
- Review routing
- Sidecar handling
- Silent-drop and bad-publish risks

Constraints followed:

- No code edits.
- Generated summaries were inspected before opening full source for subtitle, publish, config, UI, QA, and tests.
- `AGENTS.md` rules were followed: subtitle conversion/publish paths were treated as high risk, and silent subtitle loss or publish after conversion failure was reviewed as high severity.
- Output was placed under `docs/reviews/` rather than top-level markdown files.

Primary generated summaries inspected first:

- `docs/generated/PROJECT_INDEX.md`
- `docs/generated/summaries/ops/pipeline/engine/subtitles/*.ps1.md`
- `docs/generated/summaries/ops/pipeline/engine/subtitles/builders/decisions.ps1.md`
- `docs/generated/summaries/ops/pipeline/engine/publish/*.ps1.md`
- `docs/generated/summaries/ops/pipeline/entrypoints/MediaPipeline/tx3g_sidecars.ps1.md`
- `docs/generated/summaries/src/mediapipeline/pipeline/ass_to_srt_cli.py.md`
- `docs/generated/summaries/src/mediapipeline/contracts/subtitles.py.md`
- `docs/generated/summaries/src/mediapipeline/core/subtitles/*.py.md`
- `docs/generated/summaries/src/mediapipeline/core/api/commands_subtitle_qa.py.md`
- relevant subtitle and sidecar test summaries under `docs/generated/summaries/ops/pipeline/tests/` and `docs/generated/summaries/tests/python/`

Primary source areas inspected:

- `ops/pipeline/engine/subtitles/`
- `ops/pipeline/entrypoints/MediaPipeline/encode.ps1`
- `ops/pipeline/entrypoints/MediaPipeline/remux.ps1`
- `ops/pipeline/entrypoints/MediaPipeline/tx3g_sidecars.ps1`
- `ops/pipeline/engine/publish/`
- `ops/pipeline/engine/config/default_values.ps1`
- `ops/pipeline/config/MediaPipeline_config_template.psd1`
- `src/mediapipeline/pipeline/ass_to_srt_cli.py`
- `src/mediapipeline/pipeline/ass_to_srt/`
- `src/mediapipeline/contracts/subtitles.py`
- `src/mediapipeline/core/subtitles/`
- `src/mediapipeline/core/api/commands_subtitle_qa.py`
- subtitle settings UI builder and metadata contract files
- PowerShell and Python subtitle test files

Out of scope:

- Source fixes.
- Real media OCR/playback validation.
- Installing or changing OCR tools.
- Broad unrelated remediation for the dirty worktree.
