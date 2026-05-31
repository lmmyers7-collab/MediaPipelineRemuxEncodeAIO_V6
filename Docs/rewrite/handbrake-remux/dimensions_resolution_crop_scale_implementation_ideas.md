# Dimensions, Resolution, Crop, And Scale Implementation Ideas

Last updated: 2026-05-31

This note collects implementation ideas for dimensions, resolution limits,
crop, scale, and their consequences in the HandBrake/remux rewrite. It is
documentation only. It does not approve FFmpeg command changes, production
route cutover, UI persistence changes, or compatibility-code cleanup.

Any future implementation that changes real encode/remux behavior touches
AGENTS.md high-risk media-policy areas and must follow the validation ladder,
including representative real-media validation where practical.

## Current Resources

The repository already has enough structure to model dimensions safely before
execution changes are made.

| Resource | Current usefulness |
| --- | --- |
| `SourceMediaInfo` | Carries source width, height, display width, display height, aspect ratio, scan type, HDR markers, and derived dimension buckets. |
| PowerShell probe stage | Current `ffprobe` stage already captures basic width/height and can be extended to emit richer video stream facts. |
| `PresetV2.dimensions` | Already has `resolutionLimit`, `customMaxHeight`, `scalingPolicy`, `aspectPolicy`, `cropMode`, `pixelAspectMode`, `maxDirectCopyHeight`, `h264DirectCopyMaxHeight`, and `scaleMode`. |
| `EffectiveDecisionPolicy` | Already carries resolution, custom height, scaling policy, crop mode, and direct-copy height limits into the Python decision layer. |
| `app/decide/encoding_rules.py` | Already maps resolution limits to heights, treats crop as a video encode trigger, and computes planned output height with no-upscale behavior unless explicitly allowed. |
| Decision and planner tests | Already cover downscale-forces-encode, filter-forces-encode, and planned output height evidence. |
| Phase 07B dry-run executor | Can eventually be extended to validate and print crop/scale command shapes before production execution changes. |
| Existing FFmpeg bundle | Should be enough for basic `crop`, `scale`, and `setsar` filters, but capabilities must be verified from the bundled binary before relying on optional filters. |

Current gap: Python can model downscale/crop consequences, but production
PowerShell encode command generation does not yet have a first-class,
validated crop/scale filter builder. Phase 07B dry-runs also do not yet prove
concrete crop/scale argument parity.

## Required Or Optional Tools

Basic implementation can use the bundled FFmpeg and ffprobe, but capability
checks should be explicit.

| Need | Current or required tool |
| --- | --- |
| Source width/height | Existing ffprobe stage. |
| Display aspect / sample aspect | Extend ffprobe `show_entries` to include `sample_aspect_ratio`, `display_aspect_ratio`, pixel format, field order, and color tags. |
| Basic scale/crop | Bundled FFmpeg `scale`, `crop`, and `setsar` filters, verified with `ffmpeg -filters`. |
| Auto crop detection | Optional FFmpeg prepass with `cropdetect`, bounded by sample count/time and disabled by default until validated. |
| Better scaling/color handling | Optional `zscale`, `scale_cuda`, `scale_npp`, `scale_qsv`, or other hardware/software filters only if the bundled FFmpeg advertises them. |
| HDR tone mapping | Separate future policy. Do not mix tone mapping into basic resize unless explicitly scoped and validated. |
| Visual validation | Generated media smokes first; representative real media for final acceptance. |

Python should not run FFmpeg to discover capabilities. It should consume
capability facts produced by a PowerShell/backend capability probe or a cached
tool inventory.

## Consequences To Model

Dimensions are not just cosmetic. They affect route, quality, compatibility,
and publish trust.

| Consequence | Rule of thumb |
| --- | --- |
| Crop or scale changes video pixels | Must route to video encode. Remux/copy cannot change pixels. |
| Audio-only transcode | Does not require video encode. Keep this separate from dimensions. |
| Subtitle conversion | Does not require video encode unless subtitles are burned into the video. |
| Subtitle burn-in | Requires video encode and a filter graph; Phase 07B currently rejects burn-in. |
| No upscale default | `never_upscale` should keep smaller sources at source height unless explicitly overridden. |
| Aspect preservation | Preserve display aspect by default; do not stretch sources silently. |
| Even dimensions | Encoders and chroma subsampling usually need even output dimensions. Round or pad deliberately. |
| HDR handling | Scaling/filters can lose or alter metadata unless color/HDR metadata is reapplied and validated. |
| Output size | Downscale can reduce size, but re-encode can still grow output depending on quality, bitrate, and encoder. Keep Output Size Check separate. |
| Plex compatibility | Downscale may help direct play, but encoding cost and quality loss must be visible. |
| Crop detection | Bad auto crop can remove content. Treat as reviewable evidence before enabling automatically. |

## Implementation Idea 1: Preview-Only Dimension Intent

Lowest-risk first step: expand dry-run evidence without changing execution.

Suggested additions:

- Add a `plannedDimensions` block to planned encode output or `PipelinePlan`
  output details.
- Include source storage size, source display size, requested limit, crop mode,
  scaling policy, planned output width/height, aspect policy, and whether the
  operation forces video encode.
- Add warnings for missing dimensions, non-square pixels, unknown aspect, HDR
  scaling, and planned upscale.
- Keep `canExecute=false` and `dryRunOnly=true` in Settings preview.

This can be tested with metadata fixtures only and does not need FFmpeg.

## Implementation Idea 2: Deterministic Scale Math In Python

Python can own the pure math for planned output dimensions while PowerShell
keeps concrete FFmpeg command construction.

Suggested pure helpers:

- normalize source storage size and display size;
- resolve `resolutionLimit` and `customMaxHeight`;
- apply `never_upscale` versus `allow_upscale`;
- preserve display aspect by default;
- round width/height to even values;
- report whether the output is source-sized, downscaled, upscaled, or unknown.

Possible contract fields:

```text
sourceWidth
sourceHeight
sourceDisplayWidth
sourceDisplayHeight
targetWidth
targetHeight
dimensionAction: source | downscale | upscale | unknown
aspectAction: preserve_display_aspect | set_sar | pad | custom
roundingAction: none | even_floor | even_round | pad
forcesVideoEncode: true | false
warnings: []
```

Keep crop math separate from scale math. Crop changes the input rectangle;
scale changes the output rectangle.

## Implementation Idea 3: Explicit Crop Model

Do not make auto crop a silent default. Crop is destructive if wrong.

Suggested model:

| Crop mode | Behavior |
| --- | --- |
| `off` | No crop and no crop-derived encode trigger. |
| `custom` | Operator-supplied left/top/right/bottom or x/y/width/height values; validates bounds before execution. |
| `auto` | Backend-generated crop suggestion only until accepted by operator or policy. |

Suggested fields:

```text
cropMode
cropSource: none | operator | cropdetect
cropRect
cropConfidence
cropSamples
cropForcesEncode
cropWarnings
```

Validation rules:

- reject negative crop values;
- reject crop rectangles outside source dimensions;
- reject crop output below minimum width/height;
- require even crop output dimensions unless padding is explicitly selected;
- warn when crop removes more than a configured percentage of the frame;
- require review for variable crop suggestions across samples.

## Implementation Idea 4: PowerShell Filter Builder

When execution is explicitly scoped, add a focused PowerShell filter builder
instead of spreading `-vf` strings across encode code.

Possible target:

- `engine/decide/video_filters.ps1`, or another focused `engine/process/`
  helper if the team wants command-construction ownership near the executor.

Responsibilities:

- accept a validated plan record, not raw UI values;
- build ordered FFmpeg filters such as `yadif`, `crop`, `scale`, and `setsar`;
- escape filter arguments centrally;
- return structured evidence and an argument list;
- be unit-tested independently from full encode execution.

Likely filter order for normal progressive sources:

```text
crop -> scale -> setsar
```

Likely filter order when deinterlace is active:

```text
deinterlace -> crop -> scale -> setsar
```

Do not hardcode this without tests. Interlaced, anamorphic, HDR, and subtitle
burn-in cases need explicit coverage.

Integration point:

- extend `New-EncodeAttemptPlan` or `New-EncodeFfmpegArgumentList` to accept a
  video filter argument list;
- keep codec flags in `New-EncodeVideoFlags`;
- keep filter graph construction out of the WebView.

## Implementation Idea 5: Tool Capability Probe

Before exposing executable crop/scale controls, add or extend capability
evidence.

Suggested facts:

```text
ffmpegVersion
availableVideoFilters
availableHardwareScalers
supportsScale
supportsCrop
supportsSetsar
supportsZscale
supportsTonemap
supportsHwUploadDownload
```

The existing `EncodingCapabilityFacts` pattern can receive these facts. The
backend/PowerShell side should produce them from the actual bundled FFmpeg.
The UI should render unavailable options as disabled or review-only rather
than guessing.

## Implementation Idea 6: UI Exposure

Keep the operator-facing workflow conservative.

Suggested Settings behavior:

- Source / Compatibility shows source storage dimensions, display dimensions,
  aspect, scan type, and HDR markers as read-only facts.
- Dimensions exposes target resolution and no-upscale policy before custom
  crop.
- Crop controls stay advanced until custom crop validation and preview evidence
  are strong.
- Auto crop, if added, first appears as a suggestion with sample evidence, not
  as an automatic destructive action.
- The Decision Preview shows `forces video encode` whenever crop/scale/filter
  changes pixels.
- The WebView never computes crop/scale routing locally; it renders backend
  preview evidence.

## Testing Strategy

Start with metadata and generated media, then move to real samples only when
execution behavior changes.

| Rung | Coverage |
| --- | --- |
| Python unit tests | resolution math, no-upscale, even dimensions, aspect preservation, crop bounds, warning generation. |
| Python planner tests | planned dimension evidence in `pipeline_plan.v1`; copy/remux unaffected when dimensions are source/no-op. |
| PowerShell unit tests | filter builder emits expected `-vf`/filter graph args and rejects unsafe crop/scale requests. |
| Phase 07B dry-run tests | command previews include filter args only for encode plans and never for copy/remux plans. |
| Generated media smoke | FFmpeg can produce expected dimensions from synthetic sources. |
| Browser/static tests | UI shows read-only source facts, staged dimension policy, and no-mutation preview boundaries. |
| Real-media validation | anamorphic source, letterbox/pillarbox source, interlaced source, 4K-to-1080p, HDR source, subtitle-bearing source, and a no-op dimensions case. |

Real-media validation becomes mandatory if production FFmpeg commands,
stream mapping, subtitle burn-in, audio/subtitle handling, publish/drain, or
source/scratch/output movement changes.

## Open Product Decisions

- Should target resolution be height-only, width/height, or named profiles?
- Should `customMaxHeight` be enough for first execution, or should custom
  width be modeled now?
- Should auto crop ever run automatically, or remain review-only?
- How much frame removal should require review?
- Should bad cropdetect variance block execution?
- Should aspect preservation use `setsar=1`, padding, or source SAR retention?
- Should output dimensions be rounded down, rounded nearest, or padded to even?
- Should HDR scaling be allowed before a separate HDR/tone-map policy exists?
- Should hardware scaler use be explicit per encoder backend or automatic?
- Should the first executable version support non-MKV outputs?

## Suggested Phased Path

1. Add preview-only planned-dimension evidence and pure tests.
2. Add richer ffprobe dimension/aspect facts.
3. Add capability facts for bundled FFmpeg filters.
4. Add PowerShell dry-run filter builder and Phase 07B command-shape tests.
5. Add generated-media encode smoke for scale-only.
6. Add custom crop validation and generated-media smoke.
7. Consider auto-crop suggestion prepass, disabled by default.
8. Only after the above, scope production execution changes with the high-risk
   validation ladder and representative real-media samples.
