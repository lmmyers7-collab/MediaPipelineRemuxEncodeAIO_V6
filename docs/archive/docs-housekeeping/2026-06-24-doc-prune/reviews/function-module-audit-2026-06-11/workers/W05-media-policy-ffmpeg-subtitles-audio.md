# Worker Review: W05-media-policy-ffmpeg-subtitles-audio

## Scope
- Assigned domain: media-policy-ffmpeg-subtitles-audio
- Assigned files: 43 files listed below
- Explicit exclusions: none by assignment. Coverage is partial due to the 2026-06-11 time-box stop request; exact unreviewed files and symbol groups are listed under Incomplete Coverage.

## Assigned File List

- `ops/pipeline/engine/audio/audio.ps1` (audio, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/audio/audio/stream_decisions.ps1` (audio, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/decide/codec_policy.ps1` (decide, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/decide/encode_policy.ps1` (decide, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/decide/profile_selection.ps1` (decide, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/decide/route_plan.ps1` (decide, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/decide/routing.ps1` (decide, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/decide/show_overrides.ps1` (decide, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/decide/size_policy.ps1` (decide, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/decide/stage.ps1` (decide, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/policy/folder_policy.ps1` (policy, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/probe/media_probe.ps1` (probe, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/probe/stage.ps1` (probe, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/subtitles/ass.ps1` (subtitles, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/subtitles/bdpgs.ps1` (subtitles, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/subtitles/builders.ps1` (subtitles, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/subtitles/builders/decisions.ps1` (subtitles, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/subtitles/common.ps1` (subtitles, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/subtitles/failure_records.ps1` (subtitles, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/subtitles/filtering.ps1` (subtitles, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/subtitles/language_policy.ps1` (subtitles, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/subtitles/routing_decisions.ps1` (subtitles, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/subtitles/srt.ps1` (subtitles, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/subtitles/subtitles.ps1` (subtitles, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/subtitles/tx3g.ps1` (subtitles, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/subtitles/vobsub.ps1` (subtitles, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/decide/__init__.py` (decide, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/decide/encoding_rules.py` (decide, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/decide/processing_decision.py` (decide, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/decide/routing.py` (decide, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/decide/routing_facts.py` (decide, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/decide/routing_outputs.py` (decide, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/decide/routing_profiles.py` (decide, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/decide/routing_size_policy.py` (decide, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/decide/routing_trace.py` (decide, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/decide/stream_actions.py` (decide, high, code-symbol-review, summary=yes)
- `src/mediapipeline/pipeline/ass_to_srt/ass_events.py` (subtitles, high, code-symbol-review, summary=yes)
- `src/mediapipeline/pipeline/ass_to_srt/log.py` (subtitles, high, code-symbol-review, summary=yes)
- `src/mediapipeline/pipeline/ass_to_srt/srt.py` (subtitles, high, code-symbol-review, summary=yes)
- `src/mediapipeline/pipeline/ass_to_srt/styles.py` (subtitles, high, code-symbol-review, summary=yes)
- `src/mediapipeline/pipeline/ass_to_srt/text.py` (subtitles, high, code-symbol-review, summary=yes)
- `src/mediapipeline/pipeline/ass_to_srt/timing.py` (subtitles, high, code-symbol-review, summary=yes)
- `src/mediapipeline/pipeline/ass_to_srt_cli.py` (subtitles, high, code-symbol-review, summary=yes)

## Coverage Ledger

| File | Symbols reviewed | Coverage | Notes |
|---|---:|---|---|
| `ops/pipeline/engine/audio/audio.ps1` | 9 | complete | Reviewed: no findings. |
| `ops/pipeline/engine/audio/audio/stream_decisions.ps1` | 12 | complete | Reviewed: no findings. |
| `ops/pipeline/engine/decide/codec_policy.ps1` | 5 | complete | Reviewed: no findings. |
| `ops/pipeline/engine/decide/encode_policy.ps1` | 0 | pending | Summary read only; source-level FFmpeg encode command review not completed. |
| `ops/pipeline/engine/decide/profile_selection.ps1` | 4 | partial | Size-guard/profile metadata reviewed; Finding W05-001 references this file. Other profile hint paths not fully reviewed. |
| `ops/pipeline/engine/decide/route_plan.ps1` | 6 | complete | Reviewed: no findings. |
| `ops/pipeline/engine/decide/routing.ps1` | 7 | partial | Route-size and route-plan integration snippets reviewed; non-size route branches not fully reviewed. |
| `ops/pipeline/engine/decide/show_overrides.ps1` | 3 | complete | Reviewed: no findings. |
| `ops/pipeline/engine/decide/size_policy.ps1` | 3 | partial | Size-guard fallback path reviewed; other size policy helper details not fully reviewed. |
| `ops/pipeline/engine/decide/stage.ps1` | 2 | complete | Reviewed: no findings. |
| `ops/pipeline/engine/policy/folder_policy.ps1` | 3 | partial | Routing size_guard_mode handling reviewed; Finding W05-001. Other folder policy branches not fully reviewed. |
| `ops/pipeline/engine/probe/media_probe.ps1` | 0 | pending | Summary read only; ffprobe/probe implementation not source-reviewed. |
| `ops/pipeline/engine/probe/stage.ps1` | 0 | pending | Summary read only; probe stage wiring not source-reviewed. |
| `ops/pipeline/engine/subtitles/ass.ps1` | 1 | partial | Summary and small symbol probes only; ASS conversion/preservation helper review not completed. |
| `ops/pipeline/engine/subtitles/bdpgs.ps1` | 8 | complete | Reviewed: no findings. |
| `ops/pipeline/engine/subtitles/builders.ps1` | 8 | partial | Burn-in/conversion/MP4 sidecar paths reviewed; Finding W05-002. Some middle function branches were not fully reviewed. |
| `ops/pipeline/engine/subtitles/builders/decisions.ps1` | 7 | complete | Reviewed: no findings. |
| `ops/pipeline/engine/subtitles/common.ps1` | 0 | pending | Summary read only; common helper source review not completed. |
| `ops/pipeline/engine/subtitles/failure_records.ps1` | 0 | pending | Summary read only; failure record implementation not source-reviewed. |
| `ops/pipeline/engine/subtitles/filtering.ps1` | 2 | partial | Language/filter symbol probes only; full source review not completed. |
| `ops/pipeline/engine/subtitles/language_policy.ps1` | 0 | pending | Summary read only; language policy source review not completed. |
| `ops/pipeline/engine/subtitles/routing_decisions.ps1` | 2 | partial | Routing decision symbol probes only; full source review not completed. |
| `ops/pipeline/engine/subtitles/srt.ps1` | 0 | pending | Summary read only; SRT helper source review not completed. |
| `ops/pipeline/engine/subtitles/subtitles.ps1` | 0 | pending | Summary read only; top-level subtitle orchestration not source-reviewed. |
| `ops/pipeline/engine/subtitles/tx3g.ps1` | 10 | complete | Reviewed: no standalone finding; evidence used by Finding W05-002. |
| `ops/pipeline/engine/subtitles/vobsub.ps1` | 9 | partial | Main VobSub paths reviewed; middle OCR/error branch output was truncated before full review. |
| `src/mediapipeline/core/decide/__init__.py` | 1 | complete | Reviewed: no findings. |
| `src/mediapipeline/core/decide/encoding_rules.py` | 6 | complete | Reviewed: no findings. |
| `src/mediapipeline/core/decide/processing_decision.py` | 12 | complete | Reviewed: no findings. |
| `src/mediapipeline/core/decide/routing.py` | 8 | complete | Reviewed: no findings. |
| `src/mediapipeline/core/decide/routing_facts.py` | 7 | complete | Reviewed: no findings. |
| `src/mediapipeline/core/decide/routing_outputs.py` | 4 | partial | Output finalization/source fact paths reviewed; remaining helper paths not fully reviewed. |
| `src/mediapipeline/core/decide/routing_profiles.py` | 8 | complete | Reviewed: no findings. |
| `src/mediapipeline/core/decide/routing_size_policy.py` | 6 | complete | Reviewed: no findings. |
| `src/mediapipeline/core/decide/routing_trace.py` | 6 | complete | Reviewed: no findings. |
| `src/mediapipeline/core/decide/stream_actions.py` | 10 | complete | Reviewed: no findings. |
| `src/mediapipeline/pipeline/ass_to_srt/ass_events.py` | 8 | complete | Reviewed: no findings. |
| `src/mediapipeline/pipeline/ass_to_srt/log.py` | 3 | complete | Reviewed: no findings. |
| `src/mediapipeline/pipeline/ass_to_srt/srt.py` | 4 | partial | SRT render/merge symbols reviewed; middle helper output was truncated before full review. |
| `src/mediapipeline/pipeline/ass_to_srt/styles.py` | 8 | complete | Reviewed: no findings. |
| `src/mediapipeline/pipeline/ass_to_srt/text.py` | 9 | complete | Reviewed: no findings. |
| `src/mediapipeline/pipeline/ass_to_srt/timing.py` | 5 | complete | Reviewed: no findings. |
| `src/mediapipeline/pipeline/ass_to_srt_cli.py` | 8 | partial | Main CLI/process orchestration paths reviewed; peripheral parse/report paths not fully reviewed. |

## Findings

| ID | Severity | File | Symbol | Problem | Suggested validation |
|---|---|---|---|---|---|
| W05-001 | Medium | `ops/pipeline/engine/policy/folder_policy.ps1` | routing `size_guard_mode` allowlist | Folder/override policy drops supported `fallback_remux` size guard mode, so the configured fallback path can silently revert to defaults. | Unit coverage for folder policy and route hint propagation of `fallback_remux`; media-policy validation for oversized encode fallback behavior. |
| W05-002 | Medium | `ops/pipeline/engine/subtitles/builders.ps1` | MP4 external SRT sidecar branch | MP4 converted subtitle sidecar planning collapses ASS/BDPGS/VobSub candidates into TX3G sidecar records and selects only the first candidate. | Subtitle builder tests with multiple converted MP4 subtitle candidates, plus real-media validation for ASS/BDPGS/VobSub preservation and sidecar evidence. |

## Detailed Findings

### W05-001 - `fallback_remux` size guard mode is dropped by folder/route hint policy

- Severity: Medium
- File/line or narrow symbol: `ops/pipeline/engine/policy/folder_policy.ps1:253-255`, routing `size_guard_mode` allowlist. Cross-file evidence in `ops/pipeline/engine/decide/profile_selection.ps1:55-58` and `ops/pipeline/engine/decide/profile_selection.ps1:171-182`; behavior use in `ops/pipeline/engine/decide/size_policy.ps1:297-300`.
- Problem: `Resolve-MediaRouteSizeGuardModeName` recognizes `fallback_remux`, and the size policy only attempts remux fallback when mode equals `fallback_remux`, but folder policy and route-hint sanitization accept only `advisory`, `strict`, and `off`.
- Impact: A folder or override requesting `fallback_remux` can be silently ignored before route selection reaches size-policy enforcement. Oversized encodes that should fall back to remux may instead run under the default guard behavior, weakening a media-policy safety control.
- Evidence: `profile_selection.ps1:171-182` includes `fallback_remux` as a valid normalized size guard mode. `size_policy.ps1:297-300` gates fallback remux on `$mode -eq 'fallback_remux'`. `folder_policy.ps1:253-255` only assigns `SizeGuardMode` when the configured value is in `@('advisory','strict','off')`; `profile_selection.ps1:55-58` applies the same narrower route-hint allowlist.
- Fix direction: Add `fallback_remux` to the folder policy and route-hint allowlists, and make invalid values visible through warning/validation instead of silent defaulting. Keep the canonical mode set shared or tested so route profiles, folder policy, and size policy cannot drift.
- Validation: Add focused PowerShell tests that load a folder policy with `routing.size_guard_mode = fallback_remux`, confirm the route profile carries the mode, and exercise `Test-MediaEncodeOutputSizePolicy`/`Resolve-MediaRouteBySize` fallback behavior. Because this is media policy, rerun representative real-media validation after the fix.

### W05-002 - MP4 converted subtitle sidecars lose source-kind fidelity and only one candidate is selected

- Severity: Medium
- File/line or narrow symbol: `ops/pipeline/engine/subtitles/builders.ps1:512-519` and `ops/pipeline/engine/subtitles/builders.ps1:743-770`, MP4 external SRT sidecar branch. Cross-file evidence in `ops/pipeline/engine/subtitles/tx3g.ps1:198-204`, `ops/pipeline/engine/subtitles/tx3g.ps1:275`, and `ops/pipeline/engine/subtitles/tx3g.ps1:357`.
- Problem: The MP4 path stores ASS-derived SRT conversions in `$tx3gTracks`, then later combines `$tx3gTracks`, `$bdpgsTracks`, and `$vobSubTracks` into `$sidecarCandidates`, selects only the first candidate, and returns it under `Tx3gTracks` while emptying `BdpgsTracks` and `VobSubTracks`. The downstream sidecar record/path uses TX3G-specific naming and kind defaults.
- Impact: Converted ASS, BDPGS, and VobSub subtitle sidecars can be represented as TX3G sidecars, losing source-codec/provenance in operator evidence and manifests. When more than one preferred subtitle conversion candidate exists for MP4, only the first candidate is carried forward by this branch, which can violate the subtitle policy expectation to preserve originals and add SRT for preferred-language tracks when configured.
- Evidence: `builders.ps1:512-519` adds ASS conversion records to `$tx3gTracks` in MP4 mode. `builders.ps1:743-770` creates `$sidecarCandidates` from TX3G, BDPGS, and VobSub converted tracks, uses `Select-Object -First 1`, and returns only that selected record in `Tx3gTracks`. `tx3g.ps1:198-204` inserts a `tx3g` filename token; `tx3g.ps1:357` emits sidecar kind `tx3g_srt`, with `tx3g.ps1:275` defaulting missing codec to `mov_text`.
- Fix direction: Use a format-neutral external SRT sidecar collection that preserves source subtitle codec/conversion kind, or keep separate returned collections for ASS/BDPGS/VobSub/TX3G sidecar records. If the intended MP4 policy is single-sidecar output, make that explicit in config/operator evidence and test selection priority.
- Validation: Add subtitle builder tests for MP4 inputs with multiple preferred-language converted subtitle candidates across ASS, BDPGS, VobSub, and TX3G, asserting returned sidecar count, source-kind metadata, filename/kind, and review/failure behavior. Follow with real-media validation for representative subtitle samples.

## Test Coverage Gaps

- No tests or media runs were executed. This was a review-only audit, and the 2026-06-11 time-box update requested writing the worker file with current coverage.
- W05-001 needs focused PowerShell policy/route tests plus representative real-media validation after any media-policy fix.
- W05-002 needs focused subtitle builder/sidecar tests plus representative real-media validation after any subtitle behavior fix.
- Pending and partial files listed below still need source-level review before this worker scope can be considered complete.

## Boundary Risks

- Reviewed areas are high-risk media policy surfaces: FFmpeg route/remux/encode decisions, audio policy, subtitle conversion/preservation, stream mapping, and ASS-to-SRT helper code.
- No code, runtime media state, manifests, queue state, or release artifacts were mutated by this worker.
- W05-001 affects the media route size-guard boundary, where drift between folder policy and route enforcement can change remux/encode outcomes.
- W05-002 affects subtitle preservation/evidence boundaries for MP4 sidecar output and converted SRT provenance.

## Files With No Findings

- `ops/pipeline/engine/audio/audio.ps1` - Reviewed: no findings.
- `ops/pipeline/engine/audio/audio/stream_decisions.ps1` - Reviewed: no findings.
- `ops/pipeline/engine/decide/codec_policy.ps1` - Reviewed: no findings.
- `ops/pipeline/engine/decide/route_plan.ps1` - Reviewed: no findings.
- `ops/pipeline/engine/decide/show_overrides.ps1` - Reviewed: no findings.
- `ops/pipeline/engine/decide/stage.ps1` - Reviewed: no findings.
- `ops/pipeline/engine/subtitles/bdpgs.ps1` - Reviewed: no findings.
- `ops/pipeline/engine/subtitles/builders/decisions.ps1` - Reviewed: no findings.
- `ops/pipeline/engine/subtitles/tx3g.ps1` - Reviewed: no standalone finding; evidence used by W05-002.
- `src/mediapipeline/core/decide/__init__.py` - Reviewed: no findings.
- `src/mediapipeline/core/decide/encoding_rules.py` - Reviewed: no findings.
- `src/mediapipeline/core/decide/processing_decision.py` - Reviewed: no findings.
- `src/mediapipeline/core/decide/routing.py` - Reviewed: no findings.
- `src/mediapipeline/core/decide/routing_facts.py` - Reviewed: no findings.
- `src/mediapipeline/core/decide/routing_profiles.py` - Reviewed: no findings.
- `src/mediapipeline/core/decide/routing_size_policy.py` - Reviewed: no findings.
- `src/mediapipeline/core/decide/routing_trace.py` - Reviewed: no findings.
- `src/mediapipeline/core/decide/stream_actions.py` - Reviewed: no findings.
- `src/mediapipeline/pipeline/ass_to_srt/ass_events.py` - Reviewed: no findings.
- `src/mediapipeline/pipeline/ass_to_srt/log.py` - Reviewed: no findings.
- `src/mediapipeline/pipeline/ass_to_srt/styles.py` - Reviewed: no findings.
- `src/mediapipeline/pipeline/ass_to_srt/text.py` - Reviewed: no findings.
- `src/mediapipeline/pipeline/ass_to_srt/timing.py` - Reviewed: no findings.

## Incomplete Coverage

Coverage is partial because the user requested an immediate time-box update on 2026-06-11. Generated summaries were read for all assigned files before source access. The exact unreviewed source/symbol groups are:

| File | Unreviewed files/symbol groups | Reason |
|---|---|---|
| `ops/pipeline/engine/decide/encode_policy.ps1` | `New-EncodeAttemptPlan`, `New-EncodeFfmpegArgumentList`, `New-EncodeVideoFlags`, CPU fallback/retry/mutex paths, stream mapping and FFmpeg argument assembly. | Summary read only; time-box stopped before source review. |
| `ops/pipeline/engine/decide/profile_selection.ps1` | Non-size-guard profile hint fields and remaining route metadata helpers. | Only size guard mode/profile metadata path was reviewed for W05-001. |
| `ops/pipeline/engine/decide/routing.ps1` | Non-size route branches and full remux/encode decision flow. | Route-size integration snippets reviewed; full source review not completed. |
| `ops/pipeline/engine/decide/size_policy.ps1` | Helpers outside the `fallback_remux` size-guard fallback path. | Targeted review only for W05-001 evidence. |
| `ops/pipeline/engine/policy/folder_policy.ps1` | Folder policy branches outside routing `size_guard_mode` and nearby source/destination policy snippets. | Targeted review only for W05-001 evidence. |
| `ops/pipeline/engine/probe/media_probe.ps1` | ffprobe invocation, metadata parsing, stream inventory, duration/HDR/title/integrity helpers. | Summary read only; time-box stopped before source review. |
| `ops/pipeline/engine/probe/stage.ps1` | Probe stage orchestration and handoff symbols. | Summary read only; time-box stopped before source review. |
| `ops/pipeline/engine/subtitles/ass.ps1` | ASS conversion/OCR/preservation helpers beyond small symbol probes. | Summary plus minimal symbol probes only. |
| `ops/pipeline/engine/subtitles/builders.ps1` | Some middle `Build-SubtitleArgs` branches around converted subtitle failure/collection handling, plus full integration pass. | Key burn-in/conversion/MP4 sidecar paths reviewed; source output was truncated before complete review. |
| `ops/pipeline/engine/subtitles/common.ps1` | Common path/codec/language helpers. | Summary read only; time-box stopped before source review. |
| `ops/pipeline/engine/subtitles/failure_records.ps1` | Failure record shape and review-routing helper implementation. | Summary read only; time-box stopped before source review. |
| `ops/pipeline/engine/subtitles/filtering.ps1` | Full subtitle filter/language selection logic. | Symbol probes only; full source review not completed. |
| `ops/pipeline/engine/subtitles/language_policy.ps1` | Preferred-language normalization and policy helpers. | Summary read only; time-box stopped before source review. |
| `ops/pipeline/engine/subtitles/routing_decisions.ps1` | Full subtitle routing decision logic. | Symbol probes only; full source review not completed. |
| `ops/pipeline/engine/subtitles/srt.ps1` | SRT helper implementation. | Summary read only; time-box stopped before source review. |
| `ops/pipeline/engine/subtitles/subtitles.ps1` | Top-level subtitle orchestration entry points. | Summary read only; time-box stopped before source review. |
| `ops/pipeline/engine/subtitles/vobsub.ps1` | Middle OCR/error branches around conversion and failure handling. | Main paths reviewed, but source output was truncated before complete review. |
| `src/mediapipeline/core/decide/routing_outputs.py` | Helper paths outside output finalization/source fact review. | Targeted review only; full source review not completed. |
| `src/mediapipeline/pipeline/ass_to_srt/srt.py` | Middle SRT rendering/merge helper details. | Source output was truncated before complete review. |
| `src/mediapipeline/pipeline/ass_to_srt_cli.py` | Peripheral CLI parse/reporting paths outside main process orchestration. | Key orchestration reviewed; full source review not completed. |
