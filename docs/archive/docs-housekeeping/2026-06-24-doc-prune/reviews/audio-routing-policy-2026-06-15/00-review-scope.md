# Audio Routing Policy Review Scope

Date: 2026-06-15

Reviewer: Codex

Change mode: documentation and review artifacts only. No production code, tests, config defaults, generated summaries, or runtime behavior were edited.

## Instructions Applied

- Followed `AGENTS.md`: read canonical project state first, inspected generated summaries before full source, kept review output under `docs/`, and added an unreleased change packet for the documentation change.
- Used an evidence-first production-audit approach: local repository facts only, source/test references with file and line anchors, and no claims based on external services.
- Treated audio policy as a no-touch/high-risk boundary per `docs/CURRENT_PROJECT_STATE.md:79`, `docs/CURRENT_PROJECT_STATE.md:224`, and `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md:73`.

## In Scope

- Current PowerShell runtime audio routing used by encode/remux:
  - `ops/pipeline/engine/audio/audio.ps1`
  - `ops/pipeline/engine/audio/audio/stream_decisions.ps1`
  - `ops/pipeline/entrypoints/MediaPipeline/remux.ps1`
  - `ops/pipeline/entrypoints/MediaPipeline/encode.ps1`
- Audio policy configuration and ownership:
  - `ops/pipeline/engine/config/choice_registry.ps1`
  - `ops/pipeline/engine/config/runtime_config.ps1`
  - `ops/pipeline/engine/config/default_values.ps1`
  - `ops/pipeline/config/MediaPipeline_config_template.psd1`
  - `ops/pipeline/config/profiles/Default.psd1`
  - `src/mediapipeline/contracts/config.py`
  - `src/mediapipeline/core/config/preview.py`
  - `src/mediapipeline/core/config/option_policy.py`
  - `src/mediapipeline/core/config/preset_migration.py`
- Python decision, preview, and future planner execution surfaces:
  - `src/mediapipeline/contracts/decision_policy.py`
  - `src/mediapipeline/core/decide/encoding_rules.py`
  - `src/mediapipeline/core/decide/routing.py`
  - `src/mediapipeline/core/decide/processing_decision.py`
  - `ops/pipeline/engine/process/pipeline_plan_executor.ps1`
- Folder and file overrides:
  - `ops/pipeline/engine/policy/folder_policy.ps1`
  - `ops/pipeline/engine/queue/file_overrides.ps1`
  - `src/mediapipeline/core/queue/file_overrides.py`
  - `src/mediapipeline/core/api/file_overrides/selectors.py`
- Completion, sidecar, and operator evidence surfaces:
  - `ops/pipeline/engine/publish/publish_completion.ps1`
  - `src/mediapipeline/core/completed/policy.py`
  - `src/mediapipeline/core/kernel/models.py`
- Unit, integration, smoke, and risk-policy tests that cover audio routing behavior.

## Out Of Scope

- Running or changing live media pipeline jobs.
- Editing audio policy implementation.
- Validating against a real Plex server or client matrix.
- Verifying actual playback on generated media beyond repository test coverage review.
- Regenerating generated summaries for these new docs.

## Review Questions

This review specifically asked whether the current policy can:

- Silently drop audio tracks.
- Preserve tracks when policy says preserve.
- Force unnecessary audio transcoding.
- Ignore saved profile/config policy.
- Create output that is likely to force Plex transcoding.
- Fail open instead of routing to review or failure.

## Overall Result

The live PowerShell path has strong fail-closed behavior for missing audio, metadata probe failure, all-audio-dropped file overrides, per-track sidecar records, and explicit MKV default-track stamping. The highest risks are not in the core `Build-AudioArgs` happy path. They are in:

- A packaged `Default.psd1` profile that omits `AudioPassthroughProfile` while carrying legacy broad compatible codecs.
- Python decision/planner behavior that treats channel caps as a transcode trigger even though the PowerShell runtime caps only transcoded audio.
- A plan-executor path that can emit `-an` for all dropped audio without carrying the `AllowNoAudio` guard.
- MP4 single-audio selection scoring drift between the PowerShell runtime and Python preview path.
