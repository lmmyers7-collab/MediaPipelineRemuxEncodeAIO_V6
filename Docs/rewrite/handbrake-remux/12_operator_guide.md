# Phase 12 Operator Guide

Last updated: 2026-05-31

This guide explains the HandBrake/remux rewrite as it exists after Phase 12.
It describes the new Settings organization, preview model, and safety language.
It does not approve production cutover. Real jobs still execute through the
legacy PowerShell path unless a later operator-approved high-risk cutover
changes that.

## Current Status

- Settings can show backend-owned dry-run `pipeline_plan.v1` preview evidence
  for explicit `SourceMediaInfo` facts and staged Settings changes.
- The preview is labelled `Predicted pending cutover` because it is planning
  evidence, not the production executor.
- The current production authority remains the legacy PowerShell route and
  execution path.
- The preview is non-mutating: it does not save settings, launch jobs, move
  files, publish, drain pending publish, rename, clean up, or touch media.

## COPY, REMUX, And ENCODE

`COPY`, `REMUX`, and `ENCODE` are display summaries derived from per-stream
actions. They are not the source of truth by themselves.

| Summary | Meaning |
| --- | --- |
| `COPY` | Video, audio, subtitles, and container can stay unchanged. |
| `REMUX` | Video is copied, but the container or non-video streams need a mux, conversion, transcode, or drop action. |
| `ENCODE` | Video must be encoded because of codec, bitrate, dimensions, filters, subtitle burn-in, or explicit policy. |
| `REJECT` | The source is not safe or complete enough to plan for publish. |
| `UNKNOWN` | Required facts are missing or the preview cannot choose safely. |

Per-stream actions are the durable evidence:

| Stream scope | Actions |
| --- | --- |
| Video | `copy`, `encode`, `reject`, `unknown` |
| Audio | `copy`, `transcode`, `drop`, `unknown` |
| Subtitle | `copy`, `convert`, `burn`, `drop`, `unknown` |
| Container | `keep`, `remux`, `change`, `unknown` |

Audio-only transcode does not mean the video is re-encoded. Subtitle conversion
to SRT does not mean the video is re-encoded. Subtitle burn-in does require
video encode because the subtitle image/text becomes part of the video frames.

## Why Copy And Remux Come First

The pipeline is still a Plex-oriented library policy engine. Copy/remux is
preferred because it preserves source quality, avoids long encode jobs, reduces
CPU/GPU wear, and usually gives Plex a direct-play or direct-stream file when
the source is already compatible.

Encoding is the fallback or policy-driven path. It is used when source facts or
saved policy say the source cannot safely remain copied/remuxed, such as:

- incompatible video codec;
- video bitrate above the direct-copy cap;
- dimensions above a configured compatibility limit;
- requested filters or downscale;
- subtitle burn-in;
- an explicit encode policy or preset.

## Reading The Decision Preview

The Settings Summary preview combines three inputs:

- read-only source facts from `SourceMediaInfo`;
- saved Settings plus any staged patch;
- the Python dry-run planner result.

Important preview labels:

| Label | Meaning |
| --- | --- |
| `Predicted pending cutover` | This is a dry-run prediction from the new planner. It is not production execution authority yet. |
| `Dry run only: yes` | The preview cannot execute native tools or mutate files. |
| `canExecute: false` | The plan is intentionally non-executable from the Settings route. |
| `legacy_powershell` | Production jobs still run through the legacy PowerShell path. |

Use the preview to understand how a selected source would be classified after a
future cutover. Do not use it as proof that the next real job will follow the
new planner unless the future cutover gate has been explicitly approved.

## Source And Compatibility Facts

The Source / Compatibility section is read-only. It should answer: what was
detected from the file?

Typical facts include:

- container and source path identity;
- file size and duration;
- video codec, dimensions, HDR markers, scan type, and bitrate;
- audio codecs, channels, languages, and default/forced flags;
- subtitle codecs, language, text/image classification, and candidate actions;
- derived annotations such as compatible direct-copy codec or missing metadata.

Unknown or missing facts matter. Missing bitrate, unknown media type, or failed
probe should be visible and conservative rather than guessed.

## UI Sections

| Section | What to look for |
| --- | --- |
| Summary | Derived route summary, dry-run status, rollout evidence, and preview warnings. |
| Source / Compatibility | Detected facts only. These are not editable output settings. |
| Routing | Processing Strategy, route enforcement, copy/remux caps, and compatibility policy. |
| Dimensions | Resolution and direct-copy height policy. Downscale requests force encode. |
| Filters | Video filters force encode. Subtitle text cleanup can affect subtitle conversion. |
| Video / Audio / Subtitles | Encoder, target mode, speed preset, quality, audio passthrough/transcode, subtitle copy/convert/burn/drop policy. |
| Container / Size Guards | Container intent, direct-copy bitrate caps, route size limits, and Output Size Check posture. |
| Verification / Publish | Validation, Output Size Check results, publish blockers, and pending-publish guidance. |
| Presets | Preset view and existing backend Preview/Save Patch flow. |

## Dimensions And Filters

Dimensions affect routing only when policy requires a different output shape.
For example, an H.264 source under the direct-copy height cap can remain copied
or remuxed. A 4K source with a `1080p` output limit requires video encode
because the video frames must be resized.

Video filters force video encode. Examples include deinterlace, denoise,
sharpen, deblock, crop, and colorspace conversion. If a filter changes the
video image, copy/remux is no longer enough.

Subtitle filters are separate. Converting ASS/TX3G/BDPGS subtitles to SRT can
be a subtitle action without video encode. Burning subtitles into video frames
does require video encode.

## Video Settings

The rewrite uses HandBrake-like vocabulary but keeps the app's library-policy
role:

| Setting concept | Meaning |
| --- | --- |
| Video encoder | Codec/backend used only when video encode is selected. Copy/remux ignores it. |
| Target mode | `auto`, `constant_quality`, `average_bitrate`, or `max_bitrate`. |
| Quality target | CQ/CRF-like quality intent for quality-based encodes. |
| Target/max bitrate | Bitrate target or ceiling for bitrate-driven encode planning. |
| Encoder speed preset | Compression effort/speed, such as NVENC `p1`-`p7` or CPU preset equivalents. |
| Content tune | Content/behavior tuning, separate from encoder speed. |

The encoder speed preset is not the same as a content tune. Speed preset
controls encode effort and throughput. Tune adjusts behavior for content or
codec-specific intent.

Advanced controls stay collapsed by default: framerate mode, profile, level,
custom crop, pixel aspect, colorspace, raw extra flags, CPU fallback settings,
process priority, thread caps, muxer flags, and tool timeouts.

## Size, Bitrate, And Enforcement

Three concepts are intentionally separate:

| Concept | Meaning |
| --- | --- |
| Route size limit | Current legacy `EncodeThresholdGB` and `TVEncodeThresholdGB` behavior. These are source-size route limits, not target output sizes. |
| Target output size | A future/explicit output-size target. Do not infer this from legacy route thresholds. |
| Direct-copy max bitrate | A bitrate ceiling for allowing video copy/remux. If the source exceeds it, encode can be selected. |

`Route Enforcement Mode` controls how routing rules such as source-size and
bitrate limits affect copy/remux versus encode planning.

`Output Size Check` is a post-process verification/publish guard. It answers:
after an encode, did the output grow too much compared with the allowed
tolerance?

| Output Size Check action | Meaning |
| --- | --- |
| `disabled` | Do not evaluate output growth. |
| `warn_only` | Show advisory warning and continue publish safety checks. |
| `block_publish` | Model a publish blocker that parks through pending publish. This remains dry-run-only until a separate production implementation is approved. |
| `fail_job` | Fail the job before publish. This preserves current legacy `strict` behavior. |

Warn-only is not a publish blocker. Block-publish is not the same as fail-job.
Block-publish preserves output and routes trust through the pending-publish
park/drain flow; fail-job stops before publish.

## Presets And Legacy Migration

Current saved settings remain legacy-compatible. The new model adds
`PresetV2` as a versioned policy view, not as the active write format.

The current flow is:

```text
legacy config or PresetV2
-> EffectiveDecisionPolicy
-> ProcessingDecision
-> dry-run PipelinePlan
```

Legacy keys such as `RoutingProfile`, `SizeGuardMode`, `VideoCodec`,
`VideoPreset`, `VideoQuality`, and `OutputContainer` remain compatibility keys.
Unknown legacy values are preserved in the v2 adapter view instead of being
dropped. Source facts do not belong in a preset; they come from the selected
media file.

## Rollout And Rollback

The rollout resolver defaults to legacy authority:

- `PlannerRolloutStage = legacy`
- `newPlannerExecutionEnabled = false`
- `dryRunOnly = true`
- `PRESET_POLICY_WRITE_FORMAT = legacy`

Rollback for the current rewrite state is configuration-only:

1. Remove planner rollout keys or set `PlannerRolloutStage` to `legacy`.
2. Set `UsePythonPlanner`, `EnablePythonPlanner`, `EnableNewPlanner`,
   `PlannerComparisonLogging`, and `NewPlannerCutoverApproved` to false or
   remove them.
3. Confirm the Settings preview reports `legacy_powershell`,
   `newPlannerExecutionEnabled: false`, and `dryRunOnly: true`.

No media files, source files, queue state, pending-publish manifests, or output
files need rollback for Phase 12 because this phase is documentation only.

## Operator Safety Notes

- Do not treat the new planner preview as production cutover approval.
- Do not bypass pending publish when final output is unsafe.
- Do not change source/scratch/output movement behavior without the validation
  ladder and representative real-media validation.
- Do not delete source media by default.
- Do not remove compatibility code without explicit approval.
- Rerun representative real-media validation after future media-policy,
  FFmpeg, subtitle, audio, publish/drain, source movement, or cleanup changes.
