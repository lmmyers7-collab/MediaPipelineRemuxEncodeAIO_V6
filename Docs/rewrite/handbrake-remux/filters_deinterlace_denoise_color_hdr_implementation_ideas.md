# Filters, Deinterlace, Denoise, Color, And HDR Implementation Ideas

Last updated: 2026-05-31

This note collects implementation ideas for video filters, deinterlace,
denoise, color handling, and HDR transforms in the HandBrake/remux rewrite.
It is documentation only. It does not approve FFmpeg command changes,
production route cutover, settings persistence changes, or compatibility-code
cleanup.

Any executable implementation touches AGENTS.md high-risk media-policy and
FFmpeg command-generation areas. Production behavior changes require focused
unit coverage, command-shape dry-runs, generated-media smokes, and
representative real-media validation.

## Current Resources

The repo already has modeling hooks for filters, but concrete production
filter execution is not yet first-class.

| Resource | Current usefulness |
| --- | --- |
| `PresetV2.filters` | Already models `detelecine`, `deinterlace`, `denoise`, `sharpen`, `deblock`, `chromaSmooth`, `colorspace`, and subtitle text-cleanup flags. |
| `EncodingCapabilityFacts` | Already validates requested filter names against supplied capability facts. Defaults currently advertise basic deinterlace-style support only. |
| `active_video_filter_names(...)` | Converts enabled filter fields into names that force video encode. |
| `video_encode_filter_reasons(...)` | Treats active video filters and crop as encode triggers in the Python decision layer. |
| `ProcessingDecision.plannedEncodeOutput` | Can carry planned video filters as preview evidence. |
| `PipelinePlan` | Can carry abstract command preview steps without executable FFmpeg args. |
| `Phase 07B dry-run executor` | Can be extended later to print validated filter graph command previews before production execution changes. |
| `Get-HDRState` | Existing PowerShell probe helper detects HDR from color transfer. |
| `Get-SourceHdr10MasteringMetadata` | Existing PowerShell helper extracts HDR10 mastering display / MaxCLL metadata for CPU x265 HDR output. |
| `New-EncodeVideoFlags` | Existing PowerShell encode helper emits HDR-related x265/NVENC flags. |

Current gap: production encode command construction has HDR metadata handling,
but there is no focused, validated video-filter graph builder for deinterlace,
denoise, deblock, sharpen, chroma smoothing, colorspace conversion, tone
mapping, or HDR-to-SDR transforms.

## Current HDR Behavior

Current encode behavior is already cautious in a few places:

- `Do-Encode` calls `Get-HDRState` after copying the source to scratch.
- Unknown HDR detection fails/holds instead of guessing.
- HDR sources attempt to extract HDR10 mastering display and MaxCLL/MaxFALL
  evidence through `Get-SourceHdr10MasteringMetadata`.
- CPU x265 fallback can receive `hdr10=1`, `hdr10-opt=1`, `repeat-headers=1`,
  `colorprim=bt2020`, `transfer=smpte2084`, `colormatrix=bt2020nc`,
  `master-display`, and `max-cll` parameters.
- GPU/NVENC HDR output gets libav-side `-color_primaries`, `-color_trc`, and
  `-colorspace` flags.

That is metadata preservation, not a general color transform system. It does
not mean tone mapping, HDR-to-SDR conversion, Dolby Vision handling, gamut
conversion, or filter-chain color correctness is solved.

## Required Or Optional Tools

The bundled FFmpeg/ffprobe should be treated as the source of executable truth.
Python should consume capability facts; it should not probe FFmpeg directly.

| Need | Current or required tool |
| --- | --- |
| Basic source color/HDR facts | Existing ffprobe helpers, likely extended to emit color range, color primaries, matrix, transfer, mastering metadata status, side data, and pixel format. |
| Deinterlace | FFmpeg filters such as `yadif` or `bwdif`; `decomb` is UI/model vocabulary and needs a concrete FFmpeg mapping. |
| Detelecine / inverse telecine | FFmpeg `fieldmatch` plus `decimate`, or a simpler disabled/review-only posture until validated. |
| Denoise | FFmpeg `hqdn3d`, `nlmeans`, `atadenoise`, or `bm3d` if the bundled binary advertises them. |
| Sharpen | FFmpeg `unsharp`, or defer until quality validation exists. |
| Deblock | FFmpeg `deblock` or codec-specific filters if advertised. |
| Chroma smoothing/noise | Candidate filters include `chromanr` or other available chroma filters; map `chromaSmooth` only after capability proof. |
| Colorspace conversion | FFmpeg `colorspace`, `zscale`, `format`, and `setparams`, depending on target and source. |
| HDR metadata preservation | Existing x265/NVENC metadata flags plus richer source facts. |
| HDR-to-SDR tone mapping | FFmpeg `zscale` plus `tonemap`, or `libplacebo`/hardware tone-map filters only when bundled and validated. |
| Hardware filtering | Optional CUDA/QSV/OpenCL/VAAPI filter chains only if the Windows bundle advertises the required filters and device setup is tested. |

Capability probing should inspect the actual bundled FFmpeg with commands like
`ffmpeg -filters`, `ffmpeg -pix_fmts`, `ffmpeg -hwaccels`, and encoder help
where appropriate, then expose structured facts to Python.

## Consequences To Model

Filters change pixels. That makes them route-affecting.

| Consequence | Rule |
| --- | --- |
| Any active video filter | Forces video encode. Copy/remux cannot apply filters. |
| Deinterlace | Forces video encode and can alter motion/detail. Use only when source scan facts or operator policy require it. |
| Detelecine | Forces video encode and can break cadence if source is not telecined. Keep conservative. |
| Denoise | Forces video encode and can remove detail. Treat strength as quality-risk evidence. |
| Sharpen | Forces video encode and can create halos/ringing. Keep advanced. |
| Deblock | Forces video encode and can blur detail. Keep reviewable. |
| Chroma smoothing | Forces video encode and can alter color detail. Needs sample validation. |
| Colorspace conversion | Forces video encode and can damage HDR/SDR interpretation if metadata is wrong. |
| HDR preservation | Requires metadata proof and correct pixel format/profile flags. |
| HDR-to-SDR tone mapping | High-risk visual transform. Do not combine with generic color conversion casually. |
| Filter chain order | Affects output. Must be explicit and tested. |
| Output Size Check | Filtered encodes can grow or shrink unpredictably; keep verification separate from route choice. |

## Implementation Idea 1: Preview-Only Filter Intent

Lowest-risk first step: make filter consequences visible without changing
execution.

Suggested preview fields:

```text
activeVideoFilters
filterForcesVideoEncode
sourceScanType
sourcePixelFormat
sourceColorTransfer
sourceColorPrimaries
sourceColorMatrix
sourceColorRange
sourceHdrState
targetColorState
filterRiskWarnings
```

Examples:

- `deinterlace=auto` with source scan type unknown should show `review`.
- `denoise=high` should show quality-risk warning.
- `colorspace=bt709` on HDR source should show `HDR transform requires
  explicit tone-map policy`.
- no active filters should keep copy/remux eligibility unchanged.

This can be tested entirely with metadata fixtures.

## Implementation Idea 2: Filter Intent Contract

Add a pure contract for planned filter intent before building FFmpeg args.

Possible record:

```text
VideoFilterPlan
  schemaVersion
  sourceFacts
  requestedFilters
  resolvedFilters
  requiresVideoEncode
  filterGraphPreview
  unsupportedFilters
  warnings
  validationStatus
```

`resolvedFilters` should use repo-owned names, not raw FFmpeg strings:

- `deinterlace_bwdif`;
- `deinterlace_yadif`;
- `detelecine_fieldmatch_decimate`;
- `denoise_hqdn3d`;
- `denoise_nlmeans`;
- `color_preserve`;
- `color_sdr_bt709`;
- `hdr_preserve`;
- `hdr_to_sdr_tonemap`.

The PowerShell builder can later map these resolved names to concrete FFmpeg
filter graph fragments.

## Implementation Idea 3: Focused PowerShell Filter Builder

When execution is explicitly scoped, add a focused PowerShell helper instead
of embedding raw `-vf` strings in encode code.

Possible target:

- `engine/decide/video_filters.ps1`, if treated as media-policy command
  construction; or
- `engine/process/video_filter_graph.ps1`, if treated as executor command
  assembly.

Responsibilities:

- accept validated plan/filter records;
- build a deterministic FFmpeg filter graph;
- escape arguments centrally;
- report unsupported or unsafe combinations;
- return structured evidence for sidecars/Diagnostics;
- remain independently unit-tested.

Initial filter order idea:

```text
detelecine/deinterlace -> crop -> scale -> denoise -> deblock -> sharpen -> colorspace/HDR metadata/pixel-format handling
```

This order is only a starting point. The final order needs explicit tests and
real-media review, especially for interlaced, HDR, anamorphic, and noisy
sources.

## Implementation Idea 4: Deinterlace And Detelecine

Suggested policy:

| Setting | First executable mapping idea |
| --- | --- |
| `deinterlace=off` | No filter. |
| `deinterlace=auto` | Preview-only until source scan facts and detection confidence are reliable. |
| `deinterlace=yadif` | FFmpeg `yadif` if available. |
| `deinterlace=decomb` | Resolve to a tested default such as `bwdif` or `yadif`; do not pretend FFmpeg has a HandBrake `decomb` filter unless implemented. |
| `deinterlace=custom` | Advanced only; require explicit validated filter fragment or reject. |
| `detelecine=auto/custom` | Defer or require an explicit `fieldmatch,decimate` validation path. |

Needed source facts:

- `field_order`;
- `scan_type`;
- frame rate;
- whether the source reports progressive, interlaced, mixed, or unknown.

Conservative behavior:

- unknown scan type should not auto-deinterlace without review;
- progressive sources should warn if deinterlace is enabled;
- deinterlace should force video encode and appear in route reasons.

## Implementation Idea 5: Denoise, Deblock, Sharpen, Chroma

Start with preview and generated-media tests before real media.

Suggested first mappings:

| Model field | Possible FFmpeg mapping | Notes |
| --- | --- | --- |
| `denoise=low/medium/high` | `hqdn3d` presets | Fast, available in many FFmpeg builds, lower quality than heavier filters. |
| `denoise=custom` | reject or advanced explicit mapping | Avoid raw filter strings until escaping and validation exist. |
| `deblock=low/medium/high` | FFmpeg `deblock` if available | Needs capability proof and visual review. |
| `sharpen=low/medium/high` | `unsharp` presets | High risk of artifacts; keep advanced. |
| `chromaSmooth=low/medium/high` | `chromanr` or available chroma filter | Needs tool proof; do not assume exact filter exists. |

Consequences:

- every enabled filter forces video encode;
- filter strength should be recorded in the plan and sidecar evidence;
- high-strength settings should produce visible quality-risk warnings;
- noisy-source auto detection should not be introduced until there is a
  measurable, validated signal.

## Implementation Idea 6: Color And HDR Transform Policy

Separate three cases. Mixing them causes hard-to-debug output.

| Case | Meaning | First safe posture |
| --- | --- | --- |
| Preserve SDR | Keep source SDR color metadata when encoding. | Safe to model; execution still needs metadata passthrough proof. |
| Preserve HDR | Keep HDR10/PQ/HLG intent and metadata in HDR output. | Existing code partially supports HDR10 metadata preservation; extend evidence and tests before adding filters. |
| Tone-map HDR to SDR | Convert HDR source into SDR output. | Treat as separate high-risk feature with explicit policy, tool support, and real-media validation. |

Possible policy fields:

```text
colorTransformMode: preserve_source | force_bt709 | preserve_hdr | hdr_to_sdr
hdrMode: preserve | strip_to_sdr | tone_map | reject_unknown
toneMapOperator: none | hable | reinhard | mobius | bt2390 | libplacebo_default
targetColorPrimaries
targetTransfer
targetMatrix
targetRange
targetPixelFormat
```

Required safeguards:

- reject HDR transforms when source HDR state is unknown;
- warn when HDR10 mastering metadata is missing;
- keep Dolby Vision as review-only unless explicit support is added;
- record target color fields in plan/sidecar evidence;
- avoid silent HDR-to-SDR conversion.

## Implementation Idea 7: Capability Facts

Extend `EncodingCapabilityFacts` with filter and color/HDR support from the
actual bundled FFmpeg.

Possible fields:

```text
supportedVideoFilters
supportedDenoiseFilters
supportedDeinterlaceFilters
supportedColorFilters
supportedToneMapFilters
supportedHardwareFilterGraphs
supportedPixelFormats
supportedColorTransfers
supportsHdr10MetadataPreserve
supportsHdrToSdrToneMap
```

PowerShell can produce these facts from the bundled tools. Python can validate
presets and preview plans against them without invoking FFmpeg.

## Implementation Idea 8: UI Exposure

Keep the Settings UI conservative:

- show source scan type, pixel format, and HDR/color facts as read-only
  evidence;
- keep filters in the Filters tab but mark all active video filters as
  `forces encode`;
- keep denoise/sharpen/deblock/chroma smoothing behind advanced or review
  cues until generated-media and real-media evidence exists;
- show color/HDR transform policy separately from ordinary filters;
- never expose HDR-to-SDR tone mapping as a casual toggle;
- keep WebView behavior display-only: backend preview owns filter consequences.

## Testing Strategy

| Rung | Coverage |
| --- | --- |
| Python contract tests | filter fields validate, active filter names are correct, unsupported capabilities produce section-labelled issues. |
| Decision tests | each active filter forces video encode and records route reasons. |
| Planner tests | planned filter evidence appears in `pipeline_plan.v1`; no-op filters preserve copy/remux eligibility. |
| PowerShell unit tests | filter builder emits expected graph fragments and rejects unsupported/unsafe combinations. |
| Phase 07B dry-run tests | dry-run command preview includes filter graph only for encode plans. |
| Generated-media smokes | synthetic interlaced, noisy, SDR, and HDR-like samples verify output dimensions, pix_fmt, color tags, and command success. |
| Browser/static tests | UI labels active filter consequences without adding frontend routing logic. |
| Real-media validation | interlaced TV sample, telecined sample if available, noisy source, SDR source, HDR10 source, HLG source if available, and a no-filter remux control. |

For HDR/color work, real-media validation should include manual playback or
probe evidence that confirms color transfer, primaries, matrix, pixel format,
and HDR metadata behave as intended.

## Open Product Decisions

- Should `deinterlace=auto` ever execute automatically, or only warn from
  source scan facts?
- Should `decomb` map to `bwdif`, `yadif`, or stay preview-only?
- Should detelecine be included in the first executable pass or deferred?
- Which denoise filter should be the default: fast/simple `hqdn3d` or heavier
  options only when explicitly selected?
- Should sharpen/deblock/chroma smoothing remain advanced-only permanently?
- Is HDR-to-SDR tone mapping in scope for this app, or should HDR sources
  preserve HDR or route to review?
- Should Dolby Vision be rejected/reviewed until specific metadata behavior is
  defined?
- Should hardware filter graphs be allowed, or should first implementation stay
  CPU/software filter graph plus existing encoder backend?
- What sidecar evidence is required before a filtered output can be trusted?

## Suggested Phased Path

1. Expand preview-only filter/color/HDR evidence in `ProcessingDecision` and
   `PipelinePlan`.
2. Extend probe facts for scan type, field order, pixel format, color range,
   color primaries, color transfer, color matrix, and HDR side-data presence.
3. Extend capability facts for bundled FFmpeg filters and color/HDR support.
4. Add a focused PowerShell filter graph dry-run builder with unit tests.
5. Add generated-media smokes for deinterlace and simple denoise.
6. Add HDR preservation tests that protect current metadata behavior.
7. Consider color transform and HDR-to-SDR tone-map only as a separate,
   explicitly approved high-risk phase.
8. Promote production execution only after command parity, browser/static
   evidence, release checks where relevant, and representative real-media
   validation are complete.
