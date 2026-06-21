# Hardware-encoder breadth + AV1 — implementation master plan

Date: 2026-06-11
Status: in progress. Phase 0 encode-flag snapshots exist, and Phase 1 now has a
HEVC/NVENC plus libx265 descriptor parity scaffold. Dormant H.264/NVENC,
libx264, AV1/NVENC, libaom AV1, QSV, and AMF descriptor entries are cataloged
with fail-closed unsupported-HDR guards where needed but are not selected by the
active resolver. Descriptor-owned list/runtime capability-probe scaffolding exists
for the dormant catalog, the legacy NVENC startup probe now bridges through the
descriptor-backed cache, and backend probe invalidation has generic descriptor-cache
support, but hardware descriptors are not wired into active encoder selection. A
synthetic SDR runtime/topology matrix executes CPU descriptor rows and reports
hardware rows as opt-in skips by default. A pure descriptor selection resolver now
returns primary/fallback descriptors plus trace evidence, including family-consistent
CPU fallback candidates. Encode attempt plans now expose descriptor-selection
evidence for current HEVC/libx265 parity paths and explicitly mark dormant AV1
selection as not yet active, but new families are not wired into the active
`Do-Encode` ladder.
Config-key changes, fallback wiring, full hardware/HDR runtime matrix coverage, and
new encoder enablement remain incomplete.
Implementing agent: Codex
Risk class: AGENTS.md section 7 — "FFmpeg command generation and stream mapping" (highest-risk area)
Validation rung: AGENTS.md section 5 media row — release gate plus real-media validation per encoder
Effort: L (five phases; each phase is a separately scoped, separately validated session)
Authority: AGENTS.md overrides this plan wherever they disagree. This plan does not
authorize anything AGENTS.md forbids. docs/SESSION.md must be updated with a scope
block before each phase begins.

---

## 0. Rules of engagement for the implementing agent

These are binding. Read AGENTS.md sections 1-3, 5, 7, 8 before any edit.

1. **One phase per session/branch.** Each phase gets its own docs/SESSION.md scope
   block, its own change packet under `ops/release/changes/unreleased/`, and its own
   operator sign-off before the next phase starts. Do not combine phases.
2. **Never self-certify.** Every phase touches FFmpeg command generation (AGENTS.md
   section 7). Agent-side tests are necessary but not sufficient; each phase ends with
   an explicit "operator validation required" list. Do not declare a phase done.
3. **Phase 0 snapshots are the parity oracle.** If a Phase 1 refactor changes any
   Phase 0 snapshot, the refactor is wrong — not the test. Never "fix" a Phase 0
   assertion to make Phase 1 pass.
4. **No new files in banned locations.** New PowerShell goes under
   `ops/pipeline/engine/<domain>/<role>.ps1` (here: `ops/pipeline/engine/decide/`).
   New unit checks go in `ops/pipeline/tests/Unit/Invoke-*Checks.ps1`. Never create
   `Pipeline/Modules/*.*.ps1`, root markdown, or smoke wrappers outside
   `ops/scripts/smoke/`.
5. **Do not touch:** audio argument building (`Build-AudioArgs`), subtitle filtering/
   extraction, publish/pending-publish, queue, source/scratch/output movement, or
   `Get-MediaEncodeOutputMuxerName`'s container decision. Chapters/metadata/attachment
   mapping in `New-EncodeFfmpegArgumentList` (`ops/pipeline/engine/decide/encode_policy.ps1:262-309`)
   is codec-independent and must remain byte-identical in every phase; the Phase 0
   full-argument-list snapshots enforce this.
6. **String-asserted code:** `ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1:855-859`
   regex-asserts source text of `Do-Encode` and `media_probe.ps1` (HDR10 forwarding,
   `Get-SourceHdr10MasteringMetadata`). Run this check after any edit to
   `ops/pipeline/entrypoints/MediaPipeline/encode.ps1`; if a needed edit breaks an
   assertion, stop and ask the operator before changing the test.
7. **After each phase:** refresh summaries
   (`.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.refresh_summaries`),
   update the change packet, run
   `mediapipeline.tools.change_control.validate_changes --require-worktree-coverage`,
   and record the handoff in docs/SESSION.md.
8. **Token budget:** the file:line citations in section 2 are pre-verified as of
   2026-06-11. Trust them for orientation; re-verify with Grep only the specific lines
   you are about to edit. Do not re-read whole files to confirm this plan.

---

## 1. Goal and non-goals

**Goal.** Support encoders beyond NVENC HEVC + libx265: Intel QSV, AMD AMF, and AV1
(NVENC AV1, SVT-AV1, QSV AV1), selected per host capability and config, with the
existing HDR10, chapter, audio, and subtitle behavior preserved per encoder.

**Non-goals.**
- No change to remux-vs-encode routing decisions (`codec_policy.ps1` route selection,
  size/bitrate thresholds, Plex compatibility scoring). Routing decides *whether* to
  encode; this campaign only changes *what encoder* runs and *what flags* it gets.
- No change to `RemuxSafeVideoCodecs` semantics (source-codec policy, not encoder policy).
- No redesign of network coordinator/worker dispatch. Encoder resolution happens on
  the executing host only (see section 11, D8).
- No removal of any existing `VideoCodec` choice and no change to the shipped default
  (`hevc_nvenc`, `ops/pipeline/engine/config/default_values.ps1:244`).

---

## 2. Current state — verified facts (2026-06-11)

Every claim below was verified against source on 2026-06-11. Citations are exact.

### 2.1 Config fan-out for VideoCodec (already 5 choices, mostly broken)

The choice set `('hevc_nvenc','libx265','h264_nvenc','libx264','av1_nvenc')` already
exists in all of these places:

| Layer | File:line |
| --- | --- |
| PS choice registry | `ops/pipeline/engine/config/choice_registry.ps1:8-9` (`Get-MediaPipelineVideoCodecNames`) |
| PS defaults | `ops/pipeline/engine/config/default_values.ps1:244` (`VideoCodec = 'hevc_nvenc'`) |
| Python contract | `src/mediapipeline/contracts/config.py:722` (`Literal[...]`) |
| Python option policy | `src/mediapipeline/core/config/option_policy.py:91-92` |
| UI field definitions | `src/mediapipeline/core/config/metadata_parts/video_fields.py:18` |
| WebView builder | `apps/desktop/webview/static/assets/settingsView.builders.video.js:167` |
| JSON schemas | `ops/pipeline/config/schemas/media_pipeline_config.schema.json`, `src/mediapipeline/contracts/schemas/config.v1.schema.json`, `src/mediapipeline/contracts/schemas/stages.v1.schema.json` |
| Setup/validation | `ops/pipeline/config/setup/ConfigFile.ps1`, `ops/pipeline/config/setup/Validation.ps1` |
| Template/profile | `ops/pipeline/config/MediaPipeline_config_template.psd1`, `ops/pipeline/config/profiles/Default.psd1` |

**Critical trap: only `hevc_nvenc` (with `libx265` fallback) actually works.** The
flag builder (2.2) emits NVENC-HEVC-shaped flags for *every* non-CPU selection:

- `libx264` selected: GPU branch emits `-preset p7` (not an x264 preset) and `-cq`
  (not an x264 option) — runtime failure.
- `h264_nvenc` + HDR source: emits `-profile:v main10` — invalid for H.264 — failure.
- `av1_nvenc`: emits `-profile:v main10` (invalid for AV1; AV1 Main profile covers
  10-bit) and HEVC-shaped tuning flags on safe retry — failure or wrong stream.
- Any non-HEVC selection that falls back to CPU lands on `libx265` regardless of
  requested family (2.3) — silent codec-family flip.

This is why the campaign exists. It also means extending behavior for the four broken
choices is **not** a behavior regression — but the `hevc_nvenc`/`libx265` paths must
stay byte-identical until Phase 3 deliberately changes documented cases.

### 2.2 The flag builder — `New-EncodeVideoFlags`

`ops/pipeline/engine/decide/encode_policy.ps1:124-260`. Structure:

- Ladder profile (`Get-MediaEncodeLadderProfile`, lines 35-94): five named ladders,
  each contributing `quality_delta`, `maxrate`, `bufsize`, `tuning_preset`.
- Quality bounding: `Get-MediaEncodeBoundedQuality` (lines 114-122), clamps to 14-32.
- CPU half-delta rule (lines 152-161): CRF gets only half the NVENC ladder delta,
  rounded AwayFromZero. Precedent for per-encoder rate-control scaling.
- GPU branch (lines 233-237): `-c:v $VideoCodec -preset $VideoPreset -cq <bounded>`
  `-maxrate <ladder> -bufsize <ladder>` + extra/tuning flags. NVENC semantics
  hardwired regardless of which codec name was selected.
- CPU branch (lines 173-231): always `-c:v libx265 -preset <CpuEncodePreset> -crf
  <bounded>` + `-x265-params` (log-level, optional pools/frame-threads via
  `CpuMaxThreads`, and the HDR block). VBV pair deliberately dropped on CPU
  (comment lines 173-179) — precedent for per-encoder VBV policy.
- HDR block, CPU side (lines 197-221): `hdr10=1`, `hdr10-opt=1`, `repeat-headers=1`,
  `colorprim=bt2020`, `transfer=smpte2084`, `colormatrix=bt2020nc`, plus
  `master-display=` / `max-cll=` strings when supplied.
- HDR block, common (lines 239-257): CPU gets `-profile:v main10 -pix_fmt p010le`;
  GPU gets that plus libav-side `-color_primaries/-color_trc/-colorspace` (NVENC
  reads color metadata from libav side; D6 comment). SDR gets `-profile:v main`.
- Safe-retry tuning (lines 165-171): replaces extra flags with
  `Get-MediaPipelineEncodeTuningFlags -Preset 'compatibility' -Codec $VideoCodec`
  (defined `ops/pipeline/engine/config/default_values.ps1:107`).

### 2.3 Attempt plans and the fallback ladder

- `New-EncodeAttemptPlan` (`encode_policy.ps1:346-482`) builds the three plan shapes
  (`primary`, `hardware_safe_retry`, `cpu_fallback`) with telemetry fields
  `SelectedEncoder`, `EncoderKind`, `SelectedGpuDevice`, `EncodeLadder`, `CpuPreset`.
  Sidecar consumers read these (recorded at
  `ops/pipeline/entrypoints/MediaPipeline/encode.ps1:79-105`); changes must be additive.
- `Get-EncodeEncoderKind` (`encode_policy.ps1:322-335`) **already classifies**
  `nvenc`, `amf`, `qsv`, `cpu` from the encoder name.
- `Test-IsHardwareEncoderFailure` (`encode_policy.ps1:734-776`) **already carries AMF
  and QSV stderr patterns** (`MFX_ERR`, `CreateComponent.*failed`, etc.); NVENC goes
  through `Test-IsNvencError` (`ops/pipeline/engine/shared/failure_codes.ps1:570`).
- `Do-Encode` (`ops/pipeline/entrypoints/MediaPipeline/encode.ps1:7-564`) runs the
  ladder: primary GPU -> safe retry -> CPU fallback, with NVENC-specific elements:
  - probe gate `Test-NvencProbeReportsAvailable` (encode.ps1:150),
  - probe-cache invalidation after double failure (encode.ps1:259-267),
  - CPU mutex `Acquire-CpuEncodeMutex` (encode.ps1:329-347),
  - CPU-aware scratch-space recheck `-IsCpuEncode` (encode.ps1:291),
  - fallback events hardcode `to_encoder = Get-MediaVideoCodecLibx265Name`
    (encode.ps1:156, 274, 387, 428),
  - route reason codes `gpu_unavailable_cpu_only` / `hardware_encoder_cpu_fallback`
    (encode.ps1:361-367) and `route_actions.video = 'encode_software'` mutation
    (encode.ps1:373-381).
- `Test-NvencAvailable` (`encode_policy.ps1`): legacy wrapper over the
  descriptor-backed list/runtime probe cache. It still exposes
  `$script:NvencAvailableProbe`, requires an exact `-encoders` match for the
  configured `TestEncoder`, then runs the descriptor's 1-frame lavfi null encode;
  invalidation helper keeps later files on CPU fallback after runtime failure.

### 2.4 HDR10 metadata source

`Get-SourceHdr10MasteringMetadata` (`ops/pipeline/engine/probe/media_probe.ps1:285`)
ffprobes first-frame `side_data_list` and returns **x265-formatted** strings:
`master-display=G(x,y)B(x,y)R(x,y)WP(x,y)L(max,min)` and `max-cll="X,Y"`.
`Do-Encode` probes once per file (encode.ps1:64-75) and forwards to every plan build.

### 2.5 Python capability model (already anticipates this campaign)

`src/mediapipeline/core/config/encoding_capabilities.py`:
- `EncodingCapabilityFacts` (lines 31-61): `supported_video_codecs`
  (default `h264/h265/hevc`), `supported_encoder_backends`
  (default `nvenc/x264/x265/copy`), containers, filters, audio, subtitle converters.
- `_check_video` (lines 107-120) already validates `encoder_backend` against facts
  and has an AV1 family check (line 119-120).
- Docstring: "PowerShell and FFmpeg remain the authority for actual executable
  support" — the facts are *supplied*, not probed, from Python. Keep it that way.

### 2.6 Existing tests relevant to this campaign

- `ops/pipeline/tests/Unit/Invoke-MediaRouteSelectionChecks.ps1` (480 lines):
  dot-sources `media_constants.ps1`, `routing.ps1`, `encode_policy.ps1`; throw-based
  `Assert-Equal`/`Assert-True` harness; resolves repo root four levels up and checks
  for `AGENTS.md` (lines 1-14). New unit checks must copy this harness pattern.
- `ops/pipeline/tests/Invoke-EndToEndSmokeChecks.ps1` — references `hevc_nvenc`.
- `ops/pipeline/tests/Unit/Invoke-PipelinePlanExecutorChecks.ps1` — references it too.
- `ops/pipeline/tests/Unit/Invoke-EncodeFlagPolicyChecks.ps1` pins active HEVC
  argument parity and descriptor scaffolding, including pure primary/fallback
  selection resolution and attempt-plan descriptor-selection evidence that remains
  inactive for dormant AV1.
- `ops/pipeline/tests/Unit/Invoke-EncoderCapabilityProbeChecks.ps1` verifies the
  descriptor-owned list/runtime probe scaffold, including exact encoder-list matching
  and list-only/runtime cache separation, without enabling dormant descriptors.
- `ops/pipeline/tests/Unit/Invoke-EncoderRuntimeMatrixChecks.ps1` runs one-frame
  synthetic SDR encodes through descriptor-owned flags for runtime-available CPU
  rows and leaves hardware descriptor execution opt-in via
  `MEDIAPIPELINE_ENCODER_RUNTIME_HARDWARE=1`.
- `ops/pipeline/tests/Invoke-AdversarialForceKillEncodeChecks.ps1`.
- `ops/pipeline/tests/Unit/Invoke-ConfigKeyRegistryChecks.ps1` (130 keys currently).
- Python: `tests/python/desktop/test_app_config_contract.py`,
  `test_service_config_option_policy.py`, `test_library_profiles.py`,
  `tests/python/core/contract/test_preset_policy_contract.py`,
  `tests/python/core/library/test_route_map.py`,
  `tests/python/desktop/test_network_coordinator_helpers.py`.

### 2.7 Adjacent NVENC-shaped settings keys

- `VideoPreset` choices `p1..p7` (NVENC scale) — `video_fields.py:27`,
  `config.py:723`.
- `EncodeTuningPreset` choices are NVENC-named (`balanced_nvenc`, ...) —
  `video_fields.py:55`, `option_policy.py:66-68`.
- `FallbackCpuQuality` (x265 `-crf`), `CpuEncodePreset` (x265 named presets),
  `CpuEncodeMaxThreads` — already a per-backend-key precedent for the CPU backend.

---

## 3. Target architecture — encoder descriptor matrix

New file: `ops/pipeline/engine/decide/encoder_descriptors.ps1` (engine `decide`
domain; side-effect-light, data-first, same conventions as `media_constants.ps1`).
Dot-sourced by `encode_policy.ps1` consumers via the same module-loading path that
already loads `encode_policy.ps1` (verify the loader list in
`ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1` and the test harnesses'
dot-source blocks pick up the new file).

### 3.1 Descriptor shape

`Get-MediaEncoderDescriptor -Family <hevc|av1|h264> -Backend <nvenc|qsv|amf|cpu>`
returns `$null` for unsupported pairs, else an ordered pscustomobject:

| Field | Type | Meaning |
| --- | --- | --- |
| `EncoderName` | string | exact ffmpeg `-c:v` value (`hevc_nvenc`, `libaom-av1`, `libsvtav1`, ...) |
| `Family` | string | `hevc` / `av1` / `h264` |
| `Backend` | string | `nvenc` / `qsv` / `amf` / `cpu` |
| `RateControlKind` | string | `nvenc_cq` / `x265_crf` / `aom_crf` / `svtav1_crf` / `qsv_global_quality` / `amf_cqp` / `x264_crf` |
| `QualityOffset` | int | added to the family base quality before bounding (calibration hook, section 11 D5) |
| `UsesVbv` | bool | whether ladder `-maxrate/-bufsize` are emitted (true only for NVENC initially) |
| `PresetMap` | hashtable | maps operator `p1..p7` to backend-native preset tokens (section 3.4) |
| `HdrHandlerKind` | string | `libav_side_data` (NVENC) / `x265_params` / `svtav1_params` / `none` |
| `SupportsHdr10Metadata` | bool | false routes HDR sources away from this backend (section 11 D6) |
| `ProfileArgsSdr` / `ProfileArgsHdr` | array | per-encoder `-profile:v` / `-pix_fmt` token arrays |
| `ProbeEncoderName` | string | encoder name used for the 1-frame availability probe |
| `FailurePatternKind` | string | feeds `Test-IsHardwareEncoderFailure` (`nvenc`/`amf`/`qsv`/`none`) |
| `ContainerNotes` | string | documentation only (e.g. AV1-in-MP4 fine, faststart kept) |

Use plain data (hashtables/arrays), not scriptblocks — descriptors cross dot-source
scope boundaries and must serialize cleanly into logs/sidecars.

A single generic builder `New-EncoderVideoFlags -Descriptor $d ...` replaces the
two-branch body of `New-EncodeVideoFlags`; the existing function signature stays as a
compatibility wrapper that resolves the descriptor and delegates (callers in
`encode.ps1` and tests keep working unchanged).

### 3.2 The matrix (target end state)

| Family \ Backend | nvenc | qsv | amf | cpu |
| --- | --- | --- | --- | --- |
| hevc | `hevc_nvenc` (today's behavior, frozen) | `hevc_qsv` (Phase 4) | `hevc_amf` (Phase 5) | `libx265` (today's behavior, frozen) |
| av1 | `av1_nvenc` (Phase 3) | `av1_qsv` (Phase 4, optional) | `av1_amf` (Phase 5, optional) | `libaom-av1` (active enum, Phase 3) / `libsvtav1` (future enum fan-out, optional) |
| h264 | `h264_nvenc` (Phase 3 cleanup, see D7) | — | — | `libx264` (Phase 3 cleanup, see D7) |

### 3.3 Resolution semantics (back-compat is the law)

- Codec family is derived from `VideoCodec`: `hevc_nvenc|libx265 -> hevc`,
  `av1_nvenc|av1_qsv|av1_amf|libaom-av1|libsvtav1 -> av1`,
  `h264_nvenc|libx264 -> h264`.
- New key `EncoderBackend` (Phase 2), values `auto|nvenc|qsv|amf|cpu`, default `auto`.
- **`EncoderBackend = auto` (or key absent) preserves today's behavior exactly**: the
  literal `VideoCodec` encoder is the primary attempt; safe retry uses the same
  encoder with compatibility flags; CPU fallback uses the family's CPU encoder
  (until Phase 3, that is always `libx265` — see D2 for the deliberate switch).
- A concrete `EncoderBackend` resolves `(family, backend)` through the matrix. If the
  pair is unsupported or the host capability probe says unavailable, log a WARN +
  `Write-PipelineEvent` and fall through the ladder (backend -> family CPU encoder).
  Never hard-fail a file because of a backend preference.

### 3.4 Preset maps (initial values; operator may retune later)

Operator-facing `VideoPreset` stays `p1..p7` everywhere (no settings-schema churn):

| p | nvenc | qsv | amf (`-quality`) | libaom-av1 (`-cpu-used`) | libsvtav1 (`-preset`) |
| --- | --- | --- | --- | --- | --- |
| p1 | p1 | veryfast | speed | 8 | 12 |
| p2 | p2 | faster | speed | 7 | 11 |
| p3 | p3 | fast | speed | 6 | 10 |
| p4 | p4 | medium | balanced | 5 | 9 |
| p5 | p5 | slow | balanced | 4 | 8 |
| p6 | p6 | slower | quality | 2 | 6 |
| p7 | p7 | veryslow | quality | 1 | 4 |

`libx265`/`libx264` keep the existing separate `CpuEncodePreset` key (unchanged).
AV1 CPU encoders deliberately do NOT use `CpuEncodePreset` (x265 preset names are not
valid AV1 preset/speed tokens); they map from `VideoPreset` per the table.

### 3.5 Rate-control mapping (initial values; calibration required, section 10.4)

| Encoder | Flags | Quality source |
| --- | --- | --- |
| hevc_nvenc | `-cq <Q>` + VBV (FROZEN — current behavior) | `VideoQuality` + full ladder delta, bounded 14-32 |
| libx265 | `-crf <Q>`, no VBV (FROZEN) | `FallbackCpuQuality` + half ladder delta (AwayFromZero), bounded |
| av1_nvenc | `-cq <Q>` + VBV | `VideoQuality` + full ladder delta, bounded |
| libaom-av1 | `-crf <Q> -b:v 0 -cpu-used <map>`, no VBV | `FallbackCpuQuality` + 2 (QualityOffset) + half ladder delta, bounded |
| libsvtav1 | `-crf <Q>`, no VBV, `-preset <map>` | `FallbackCpuQuality` + 2 (QualityOffset) + half ladder delta, bounded |
| hevc_qsv | `-global_quality <Q>` (ICQ), no VBV | `VideoQuality` + 2 (QualityOffset) + full ladder delta, bounded |
| av1_qsv | `-global_quality <Q>`, no VBV | same as hevc_qsv |
| hevc_amf | `-rc cqp -qp_i <Q> -qp_p <Q>`, no VBV | `VideoQuality` + full ladder delta, bounded |
| libx264 | `-crf <Q>`, no VBV, `-preset <CpuEncodePreset>` | `FallbackCpuQuality` + half ladder delta, bounded |

QualityOffsets are starting points only; the per-encoder real-media calibration step
(section 10.4) is the authority. Record final values in the descriptor and the change
packet.

### 3.6 HDR10 handling per descriptor

| HdrHandlerKind | Encoders | Mechanism |
| --- | --- | --- |
| `libav_side_data` | hevc_nvenc, av1_nvenc | Current GPU-branch behavior: `-profile/-pix_fmt p010le` + `-color_primaries bt2020 -color_trc smpte2084 -colorspace bt2020nc`; NVENC consumes mastering metadata from libav side data (encode_policy.ps1:239-254 comment). For av1_nvenc: `-pix_fmt p010le` but NO `-profile:v main10` (AV1 Main covers 10-bit; verify accepted profile tokens via `ffmpeg -h encoder=av1_nvenc`). |
| `x265_params` | libx265 | Current CPU-branch behavior (encode_policy.ps1:197-221), FROZEN. |
| `svtav1_params` | libsvtav1 | `-svtav1-params mastering-display=<G()B()R()WP()L() string>:content-light=<MaxCLL,MaxFALL>` plus `enable-hdr=1` if supported, `-pix_fmt p010le`, and libav color flags. The x265-format strings from `Get-SourceHdr10MasteringMetadata` use the same `G()B()R()WP()L()` syntax SVT-AV1 expects and `max-cll "X,Y"` maps directly to `content-light=X,Y` — but MUST be verified against the bundled ffmpeg's SVT-AV1 build (`ffmpeg -h encoder=libsvtav1`) before relying on it. |
| `none` | libaom-av1, hevc_qsv, hevc_amf, av1_qsv (until proven) | `SupportsHdr10Metadata = $false`. HDR sources never use these backends (D6). |

---

## 4. Phase 0 — characterization tests (freeze current behavior)

Status: complete for the current snapshot scope. `ops/pipeline/tests/Unit/Invoke-EncodeFlagPolicyChecks.ps1`
pins 22 encode argument/metadata cases and is the parity oracle for later phases.

**Intent:** lock today's exact FFmpeg argument lists before anything moves.
**Production code changed: none.** This phase only adds a test file.

### 4.1 In-scope files

- NEW `ops/pipeline/tests/Unit/Invoke-EncodeFlagPolicyChecks.ps1`
- `docs/generated/summaries/` mirror for the new file
- Change packet

### 4.2 What to build

Copy the harness pattern of `Invoke-MediaRouteSelectionChecks.ps1:1-45` (repo-root
resolution, `AGENTS.md` check, throw-based asserts). Dot-source, in order:
`ops/pipeline/engine/shared/media_constants.ps1`,
`ops/pipeline/engine/config/default_values.ps1` (for
`Get-MediaPipelineEncodeTuningFlags`, `Get-MediaPipelineEncodeLadderNames`,
`Resolve-MediaPipelineCpuEncodePreset` — verify which of these live there and add
whatever file defines the rest), `ops/pipeline/engine/decide/encode_policy.ps1`.

Snapshot `New-EncodeAttemptPlan(...).ArgumentList` joined with `'|'` and compare to a
literal expected string for every cell of this matrix:

- Attempt: `primary`, `hardware_safe_retry` (`-UseSafeHardwareRetry`), `cpu_fallback`
  (`-UseCpuFallback`)
- HDR: SDR; HDR without metadata strings; HDR with
  `-Hdr10MasterDisplay 'G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1)'`
  and `-Hdr10MaxCll '1000,400'`
- Output: `out.mkv` and `out.mp4` (locks chapter/metadata/attachment/faststart args)
- Ladder: `auto` with `-IsTV:$false`, `tv_balanced`, `plex_compat` (locks the
  quality_delta, VBV values, and the compatibility tuning-flag injection)
- CpuMaxThreads: 0 and 8 (locks pools/frame-threads/-threads emission)
- Fixed inputs for all cases: `-VideoCodec 'hevc_nvenc' -VideoPreset 'p7'
  -VideoQuality 22 -FallbackCpuQuality 20 -CpuPreset 'medium' -GlobalTitle 'T'
  -InputPath 'in.mkv'`, plus one case with non-empty `-AudioArgs`/`-SubtitleMapArgs`
  /`-ExtraInputs`/`-VideoFilterArgs` to lock segment ordering.

Do not snapshot every cross-product cell blindly — cover each axis at least once and
each interaction that section 2.2 shows is real (ladder x CPU half-delta; safe-retry
x tuning preset; HDR x mp4). Target 20-30 named cases. Also assert plan metadata
(`Attempt`, `Route`, `Label`, `ProgressStage`, `EncoderKind`, `SelectedEncoder`,
`CpuPreset`) for the three attempt shapes, and `Test-ShouldRetryEncodeWithCpuFallback`
truth table (success/stop/ForceCpu/NVENC-stderr/AMF-stderr/QSV-stderr/garbage-stderr).

Build expected strings by RUNNING the current code and pasting the output, then
re-running to confirm determinism. Inspect each pasted string against section 2.2
before committing it — the point is to encode current behavior, reviewed.

### 4.3 Validation (agent-side, all must pass)

```
pwsh -NoProfile -File ops\pipeline\tests\Unit\Invoke-EncodeFlagPolicyChecks.ps1
pwsh -NoProfile -File ops\pipeline\tests\Unit\Invoke-MediaRouteSelectionChecks.ps1
pwsh -NoProfile -File ops\pipeline\tests\Invoke-EndToEndSmokeChecks.ps1
```

Exit criteria: new check green; zero production-file diffs (`git diff --stat` shows
only the new test + summary + packet). Operator gate: none needed (test-only), but
report the snapshot count and any surprises found while snapshotting.

---

## 5. Phase 1 — encoder-descriptor refactor (behavior-identical)

Status: partial. `ops/pipeline/engine/decide/encoder_descriptors.ps1` defines the
existing HEVC/NVENC primary and libx265 CPU fallback descriptors, plus dormant
H.264/NVENC, libx264, AV1/NVENC, libaom AV1, QSV, and AMF descriptors for
future activation work. The canonical module loader registers it before
`EncodePolicy.ps1`, and `New-EncodeVideoFlags` delegates to the descriptor path
only for the two already-supported HEVC cases. Unknown, H.264, AV1, and
not-yet-enabled encoders still use the legacy branch so Phase 0 snapshots remain
unchanged.

**Intent:** restructure `New-EncodeVideoFlags` around descriptors without changing a
single emitted argument. Phase 0 snapshots prove it.

### 5.1 In-scope files

- NEW `ops/pipeline/engine/decide/encoder_descriptors.ps1` (section 3.1; populate
  ONLY the two working descriptors: `(hevc,nvenc)` and `(hevc,cpu)`)
- EDIT `ops/pipeline/engine/decide/encode_policy.ps1` — `New-EncodeVideoFlags` becomes
  a wrapper that resolves a descriptor from `($VideoCodec, $UseCpuFallback)` and
  delegates to the new generic builder. Public signature unchanged. All other
  functions in the file unchanged.
- EDIT whatever loader dot-sources `encode_policy.ps1` so `encoder_descriptors.ps1`
  loads first (check `ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1` and
  `ops/pipeline/engine/decide/routing.ps1`'s own dot-source chain; mirror how
  `codec_policy.ps1` is pulled in — see its header comment, `codec_policy.ps1:4-5`).
- EDIT test harness dot-source blocks that load `encode_policy.ps1` directly
  (`Invoke-MediaRouteSelectionChecks.ps1:12-14`, the new Phase 0 file, and any other
  Unit checks that dot-source it — grep `decide\\encode_policy.ps1` under
  `ops/pipeline/tests/`).
- Summaries + change packet.

### 5.2 Constraints

- `Do-Encode` (`encode.ps1`) — **zero edits this phase.**
- Resolution rule inside the wrapper for unknown encoder names (e.g. `libx264`,
  `h264_nvenc`, `av1_nvenc`, arbitrary strings): fall through to the EXACT current
  code path (NVENC-shaped GPU branch / x265 CPU branch) so even the broken combos
  stay bit-identical this phase. The descriptor lookup only intercepts
  `(hevc,nvenc)` and `(hevc,cpu)`.
- No new config keys this phase.

### 5.3 Validation

Same three commands as Phase 0 (snapshots must pass UNCHANGED), plus:

```
pwsh -NoProfile -File ops\pipeline\tests\Unit\Invoke-PipelinePlanExecutorChecks.ps1
pwsh -NoProfile -File ops\pipeline\tests\Legacy\Invoke-LegacyDesktopReliabilityRegressionChecks.ps1
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.ai_guardrail
```

Operator gate (section 7 — not self-certified): one representative real-media encode
(HDR HEVC source) confirming identical encoder flags in the pipeline log vs a
pre-refactor run, or explicit operator waiver given the snapshot parity.

---

## 6. Phase 2 — capability detection + `EncoderBackend = auto`

**Intent:** know what the host can run, expose it, and add the backend key — without
changing any default encode behavior.

### 6.1 Capability probe (PowerShell, executing host)

- Generalize `Test-NvencAvailable` (`encode_policy.ps1:484-598`) into
  `Test-EncoderBackendAvailable -Backend <nvenc|qsv|amf> [-Force]` in
  `encoder_descriptors.ps1` or a sibling `encoder_probe.ps1` (decide domain):
  same two steps — `-encoders` list regex for that backend's encoder names, then a
  1-frame lavfi null encode of the descriptor's `ProbeEncoderName`. Per-backend cache
  hashtable `$script:EncoderBackendProbes[<backend>]` with the same result shape
  (`Available/Probed/Reason/EncoderListMatch/RuntimeOk/ProbedAt`).
- `Test-NvencAvailable` is now a legacy wrapper over the descriptor probe cache.
  `Invalidate-NvencAvailableProbe` delegates to `Invalidate-EncoderBackendProbe` for
  the NVENC backend, and `Test-NvencProbeReportsAvailable` still exposes the existing
  NVENC cache semantics required by `Do-Encode`; keep their names.
- `Invalidate-EncoderBackendProbe -Backend ... -Reason ...` exists and emits the same
  `gpu_unavailable` pipeline event shape with an additive `backend` field in `Data`.
- Capability report: after probing, write a JSON report (encoder name -> available/
  reason/probedAt) into the same runtime-state directory `Save-Progress` uses (find
  it in `ops/pipeline/engine/status/progress_state.ps1`; it lives under `LocalBase/`,
  which is gitignored). Name: `encoder_capabilities.json`. Add a read-only
  entrypoint switch `-DumpEncoderCapabilitiesPath <path>` to `MediaPipeline.ps1`
  mirroring the existing `-DumpEffectiveConfigPath` switch (no singleton lock —
  copy that switch's pattern exactly; it was added 2026-06-03, see docs/SESSION.md
  handoff for context). Probe lazily: only the backends the resolved config can
  actually select, and only when encode work is possible (do not slow `-ValidateOnly`).

### 6.2 `EncoderBackend` key (settings schema — section 7 area, operator gate)

New key, default `'auto'`, choices `auto|nvenc|qsv|amf|cpu`. Full fan-out checklist —
every row is mandatory; `Invoke-ConfigKeyRegistryChecks.ps1` and the contract tests
will catch most omissions:

1. `ops/pipeline/engine/config/default_values.ps1` — default + (if needed) tuning-map
   awareness.
2. `ops/pipeline/engine/config/choice_registry.ps1` — `Get-MediaPipelineEncoderBackendNames`.
3. The config-key registry that `Invoke-ConfigKeyRegistryChecks.ps1` validates
   (discover via that script; currently 130 keys).
4. `ops/pipeline/config/MediaPipeline_config_template.psd1` + `ops/pipeline/config/profiles/Default.psd1`.
5. `ops/pipeline/config/setup/ConfigFile.ps1` + `ops/pipeline/config/setup/Validation.ps1`.
6. `ops/pipeline/config/schemas/media_pipeline_config.schema.json`.
7. `src/mediapipeline/contracts/config.py` (+ regenerate
   `src/mediapipeline/contracts/schemas/config.v1.schema.json` with the project's
   schema generation tool — grep `mediapipeline.tools` for the generator; do not
   hand-edit generated schemas).
8. `app/kernel/config_keys.py` — `KEY_ENCODER_BACKEND` constant.
9. `src/mediapipeline/core/config/option_policy.py` — choice validation.
10. `src/mediapipeline/core/config/metadata_parts/video_fields.py` — UI field def
    (page Video, section "NVENC / Encode" -> rename to "Encoder" is OUT of scope;
    keep section name).
11. WebView: `settingsView.builders.video.js` (+ `page-settings.html`,
    `settingsMetadata.js` if field lists are mirrored there — grep `VideoCodec` in
    `apps/desktop/webview/static/` and mirror every hit).
12. `docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md`.
13. Tests: `test_app_config_contract.py`, `test_service_config_option_policy.py`,
    `Invoke-ConfigKeyRegistryChecks.ps1`, webview settings smokes.

### 6.3 Resolution wiring

- New pure function `Resolve-EncoderSelection -VideoCodec <s> -EncoderBackend <s>
  -CapabilityProbe <scriptblock|results>` returning
  `{ PrimaryDescriptor, CpuFallbackDescriptor, ResolutionTrace }`.
  `auto` returns the literal-VideoCodec descriptor chain (section 3.3) — today's
  behavior. Unit-test exhaustively in the Phase 0 check file (new section).
- `Do-Encode` consumes the resolution ONLY to pick `$VideoCodec`-equivalent values it
  already passes; with `auto` + `hevc_nvenc` the emitted commands must equal Phase 0
  snapshots (assert via smoke + log diff).
- Python: thread capability facts from the report into
  `validate_encoding_capabilities` callers (grep callers of
  `EncodingCapabilityFacts`); UI choice filtering = annotate unavailable encoders in
  `choice_help` ("not detected on this machine") — never remove choices (settings
  round-trip safety; a config written on machine A must still load on machine B).

### 6.4 Validation

Phase 0/1 commands, plus:

```
pwsh -NoProfile -File ops\pipeline\tests\Unit\Invoke-ConfigKeyRegistryChecks.ps1
pwsh -NoProfile -File ops\pipeline\tests\Unit\Invoke-ContractSchemaChecks.ps1
.\apps\desktop\runtime\Python\python.exe -m pytest tests\python\desktop\test_app_config_contract.py tests\python\desktop\test_service_config_option_policy.py -q
pwsh -File ops\pipeline\entrypoints\MediaPipeline.ps1 -ValidateOnly   (must stay clean)
```

Operator gate: settings save/load round-trip in the GUI with the new key; confirm
`-DumpEncoderCapabilitiesPath` output on the real host (expect nvenc=true on the
operator's RTX machine); pending-publish/queue smokes for regression
(`ops/scripts/smoke/Test-WebView*`, `Test-LocalApi*`).

---

## 7. Phase 3 — AV1 (libaom/libsvt + av1_nvenc) — first new encoders

**Intent:** biggest payoff first. CPU AV1 is deterministic to validate, while
av1_nvenc requires an RTX 40-series or newer-capable NVIDIA path (the probe decides
at runtime).

### 7.1 Scope

- Populate descriptors for the active config enum first: `(av1, cpu) = libaom-av1`
  and `(av1, nvenc) = av1_nvenc` per sections 3.4-3.6. The bundled ffmpeg also
  advertises `libsvtav1`; adding `libsvtav1` as a selectable config value is a
  separate enum fan-out change. Verify flag names against the BUNDLED ffmpeg first:
  `ffmpeg -h encoder=libaom-av1`, `ffmpeg -h encoder=libsvtav1`,
  `ffmpeg -h encoder=av1_nvenc`, `ffmpeg -encoders`. Locate the bundled binary the
  same way the pipeline does (`$script:ffmpegPath` resolution — grep `ffmpegPath`
  in `ops/pipeline/engine/`). If the bundled build lacks the selected CPU AV1
  encoder, STOP and report to the operator (tool upgrade is its own §7 decision; do
  not swap ffmpeg builds yourself).
- `av1_nvenc`, `av1_qsv`, `av1_amf`, and `libaom-av1` are already in the active
  config enum. Extending choices with `libsvtav1`, if desired, requires the full
  section 2.1 fan-out table and is separate from activating the existing
  `libaom-av1` path.
- **Family-consistent CPU fallback (deliberate behavior change, D2):** when the
  resolved family is `av1`, the CPU fallback descriptor is the selected CPU AV1
  descriptor (`libaom-av1` for the active enum unless a later `libsvtav1` fan-out is
  approved), not `libx265`. `hevc`-family files keep `libx265` byte-identical.
  Implement in `Resolve-EncoderSelection`; surface in `Do-Encode` fallback events
  (`to_encoder` becomes the descriptor's `EncoderName` instead of the hardcoded
  `Get-MediaVideoCodecLibx265Name` at encode.ps1:156/274/387/428 — this edit hits
  legacy string assertions; see rule 6 in section 0).
- CPU-encode plumbing that must apply to the selected CPU AV1 encoder exactly as it does to libx265
  (these are keyed off `UseCpuFallback`, so verify they trigger, not rebuild them):
  CPU mutex, `-IsCpuEncode` scratch recheck, `FFmpegCpuEncodeTimeoutSeconds`,
  `CpuEncodeProcessPriority`, `encode_cpu` progress stage. `CpuMaxThreads` is
  x265-params-specific; for `libaom-av1` emit only libav `-threads N` plus
  `-cpu-used <map>`. For optional `libsvtav1`, emit only libav `-threads N` and
  `-svtav1-params lp=N` if the bundled build supports it — verify first.
- HDR10: keep `libaom-av1` fail-closed until HDR10 metadata preservation is proven.
  For `av1_nvenc`, use the `libav_side_data` handler minus `-profile:v main10`
  (verify accepted `-profile` tokens; omit the flag entirely if unclear — AV1 Main
  supports 10-bit). Optional `libsvtav1` activation needs a verified
  `svtav1_params` handler (section 3.6).
- Failure detection: confirm `Test-IsNvencError` patterns cover av1_nvenc failures
  (they should — same NVENC driver layer); add CPU AV1 stderr pattern sets only if
  real failures prove undetected (CPU failures route through generic ffmpeg failure
  codes today).
- Sidecar/telemetry: `EncoderKind` for `libaom-av1`/`libsvtav1` currently returns
  `software_or_unknown` (`Get-EncodeEncoderKind`, encode_policy.ps1:322-335) — add
  AV1 CPU encoder mappings to `cpu` when activation begins (additive; assert in
  unit checks).
- Size policy: `Test-MediaEncodeOutputSizePolicy` consumes route reason codes, not
  encoder names (encode.ps1:468-476) — confirm no change needed; AV1 outputs are
  expected SMALLER, so the growth guard is safe. Do not touch routing thresholds.

### 7.2 Tests

- Phase 0 file: new snapshot sections for `(av1,cpu)` and `(av1,nvenc)` x
  SDR/HDR(with metadata)/mp4/ladders, written the same run-and-paste way; existing
  hevc snapshots UNCHANGED.
- `Invoke-MediaRouteSelectionChecks.ps1`: extend attempt-plan metadata assertions for
  av1 plans (Route/Label/ProgressStage unchanged shapes; `SelectedEncoder`,
  `EncoderKind` correct).
- Python: extend `option_policy` / contract tests for the new enum member.
- Existing scaffold check: `Invoke-EncoderCapabilityProbeChecks.ps1` covers exact
  encoder-list matching and one-frame lavfi runtime probing for descriptor-owned
  availability helpers. It is not the full runtime matrix required before enabling
  new encoder families.
- Existing scaffold check: `Invoke-EncoderRuntimeMatrixChecks.ps1` runs synthetic SDR
  descriptor-topology encodes for CPU rows and reports hardware rows as opt-in skips
  unless `MEDIAPIPELINE_ENCODER_RUNTIME_HARDWARE=1` is set. It is not representative
  real-media validation and does not cover HDR preservation.

### 7.3 Validation (this is the strictest rung — release gate + real media)

Agent-side: all prior commands, plus targeted 5-10s lavfi clip encodes through the
bundled ffmpeg for each new descriptor (SDR + HDR10 synthetic) asserting exit 0 and
`ffprobe` shows: correct codec, 10-bit pix_fmt for HDR-capable descriptors,
mastering-display/CLL side data present only for descriptors whose HDR handler claims
metadata preservation, chapters preserved (mkv), faststart (mp4). Put these in a NEW
`ops/pipeline/tests/Unit/Invoke-EncoderRuntimeMatrixChecks.ps1` that SKIPS (with a
clear message, exit 0) any backend the host probe reports unavailable.

Operator-side (required, not self-certified):
- `.\ops\scripts\release\test.ps1` (release gate).
- Real-media worksheet via `.\ops\scripts\operator\New-RealMediaValidationWorksheet.ps1`:
  at least one HDR10 movie and one TV episode per new encoder; verify Plex
  direct-play, HDR metadata in `ffprobe`, subtitle/audio/chapter parity with an
  hevc_nvenc control encode, and size/quality acceptability.
- Quality/size calibration (section 10.4) — adjust `QualityOffset` from evidence.

---

## 8. Phase 4 — Intel QSV; Phase 5 — AMD AMF

Same template as Phase 3, one backend per phase. Highlights only:

- **QSV (`hevc_qsv`, optionally `av1_qsv`):** rate control `-global_quality` (ICQ);
  availability detection is the fiddly part — the `-encoders` listing is necessary
  but NOT sufficient (ffmpeg can list QSV without a usable iGPU/driver); the 1-frame
  runtime probe is the authority, and on hosts with a discrete GPU plus iGPU the
  probe may need `-init_hw_device qsv=hw` — investigate against real hardware. If
  the operator has no Intel iGPU host, implement + unit-test descriptors but mark
  the backend "implemented, not host-validated" in the change packet, keep
  `SupportsHdr10Metadata=$false`, and rely on the runtime probe to gate it off.
- **AMF (`hevc_amf`):** rate control `-rc cqp -qp_i/-qp_p`; same host-availability
  caveat (no AMD GPU = implemented-not-validated). Failure patterns already exist
  (encode_policy.ps1:748-757).
- Both: HDR sources excluded (D6) until an operator-validated HDR10 carriage test
  proves otherwise; only then flip `SupportsHdr10Metadata` in a follow-up packet.
- Safe-retry semantics: `Get-MediaPipelineEncodeTuningFlags -Preset 'compatibility'`
  is NVENC-flag-shaped (`default_values.ps1:107`) — for QSV/AMF the safe retry must
  use a descriptor-supplied compatibility flag set (start with: drop lookahead/
  advanced options, force plain preset), not the NVENC bundle.

---

## 9. Cross-cutting sync points (consult on EVERY phase)

When an encoder choice or key changes, walk section 2.1's table plus:

- `src/mediapipeline/core/config/library_profile_compatibility.py` and
  `tests/python/desktop/test_library_profiles.py` (per-library VideoCodec overrides).
- `ops/pipeline/engine/queue/file_overrides.ps1` (per-file VideoCodec override).
- `src/mediapipeline/core/config/settings_wizard.py` + `settingsWizard.js`.
- `src/mediapipeline/core/config/preset_encoding_sections.py`,
  `src/mediapipeline/contracts/decision_policy.py`,
  `src/mediapipeline/contracts/stage_mutation.py`.
- `apps/desktop/webview/static/assets/settings/policyImpact.js`, `patchReview.js`.
- `docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md`.
- Summaries under `docs/generated/summaries/` for every edited source file.

Discovery command per phase (run, then reconcile every hit):
`Grep pattern "hevc_nvenc|libx265|av1_nvenc|libaom-av1|libsvtav1|hevc_qsv|hevc_amf"` repo-wide
(respect `.rgignore`).

---

## 10. Validation matrix (summary)

| Phase | Agent-side (must pass) | Operator gate (required) |
| --- | --- | --- |
| 0 | New flag-policy checks; route-selection checks; end-to-end smoke | none (test-only) |
| 1 | Phase 0 snapshots UNCHANGED; plan-executor; legacy regression; guardrail | parity log diff on one real encode (or waiver) |
| 2 | + config-key registry; contract schema; config/option pytest; `-ValidateOnly` | GUI settings round-trip; capability dump on real host; WebView/LocalApi smokes |
| 3 | + runtime matrix checks (lavfi clips, skip-if-unavailable); av1 snapshots | release gate; real-media worksheet per encoder; quality calibration |
| 4/5 | same as 3 per backend | same as 3 per backend (or "implemented, not host-validated" status) |

### 10.4 Quality/size calibration protocol (Phases 3-5)

For each new encoder, encode the same 2-3 real sources with the family control
encoder (hevc: hevc_nvenc@cq22; av1: the selected CPU AV1 descriptor is its own
baseline vs libx265 crf20) and the candidate. Record output size, encode wall time, and the operator's
subjective quality verdict in the real-media worksheet. Adjust the descriptor
`QualityOffset` so the candidate's size/quality lands at-or-better than the control.
Final offsets go in the change packet's `notes` and the descriptor file.

---

## 11. Pre-made decisions (do not re-litigate; escalate only with new evidence)

- **D1 — AV1 first, QSV/AMF after.** Phases 0-3 are the committed scope; Phases 4-5
  each require fresh operator approval to start.
- **D2 — family-consistent CPU fallback lands in Phase 3,** not earlier. Until then
  every fallback stays libx265, including the (already broken) av1/h264 selections.
- **D3 — `EncoderBackend` default `auto` = literal `VideoCodec` passthrough.**
  Absent key, absent probe, or probe failure must reproduce today's command lines
  exactly for hevc_nvenc/libx265.
- **D4 — operator-facing preset stays `p1..p7`**, mapped per descriptor (section
  3.4). No new per-backend preset keys.
- **D5 — initial QualityOffsets are placeholders** (section 3.5) pending the 10.4
  protocol. Do not invent different starting values.
- **D6 — HDR sources never route to a backend with `SupportsHdr10Metadata=$false`.**
  Silent HDR-to-SDR-ish output is a forbidden bad publish (AGENTS.md section 3
  spirit). The resolution trace must log the exclusion.
- **D7 — `h264_nvenc`/`libx264` are repaired opportunistically in Phase 3** (their
  descriptors are nearly free once the matrix exists: x264_crf/`-profile` handling,
  no main10). If they add risk to the AV1 session, split them into their own packet.
- **D8 — capability is per-executing-host.** Coordinator/worker dispatch does not
  consult encoder capabilities this campaign; a worker without the preferred backend
  falls back locally via the ladder (and logs it).
- **D9 — no new ffmpeg binary.** If the bundled build lacks an encoder, the
  descriptor stays dormant behind the probe. Tool upgrades are a separate operator
  decision.
- **D10 — `EncodeTuningPreset` keeps its NVENC-named choices** this campaign;
  non-NVENC backends ignore it except via descriptor compatibility flags (section 8).
  Renaming/generalizing those choice strings is follow-up work.

---

## 12. Risks

- **Rate-control non-portability** — top risk; mitigated by D5 + the 10.4 protocol
  and by never letting a new backend ship without operator real-media sign-off.
- **HDR10 carriage differences** — mitigated by per-descriptor handlers, D6
  exclusion, and ffprobe side-data assertions in the runtime matrix checks.
- **QSV/AMF detection flakiness** — mitigated by runtime 1-frame probe as authority,
  per-backend caches, and ladder fallback (a wrong probe degrades to CPU, never to a
  failed file).
- **Fan-out misses** (one enum updated, another not) — mitigated by the section 9
  grep ritual + config-key registry/contract checks which fail on drift.
- **Legacy string-assertion breakage** in `Do-Encode` — mitigated by rule 6
  (section 0); run the legacy check after every encode.ps1 edit.
- **Behavior drift during refactor** — mitigated by Phase 0 snapshots and the
  Phase 1 wrapper-with-fallthrough design (unknown codecs keep the old path).

## 13. Rollback

Each phase is one branch + one change packet; rollback = revert that branch. The
descriptor file is additive; Phases 2+ guard every new path behind
`EncoderBackend=auto` defaults and probe gates, so reverting a descriptor or pinning
`EncoderBackend=nvenc`/`VideoCodec=hevc_nvenc` in config restores prior behavior
without code changes. Pending-publish/queue state is untouched by all phases.
