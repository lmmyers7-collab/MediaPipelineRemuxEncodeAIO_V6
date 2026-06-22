# Dynamic HDR preservation plan — Dolby Vision RPU / HDR10+ across transcode

Status: PLAN ONLY. Written 2026-06-11 for execution by Codex in later, separately
approved sessions. Nothing in this document has been implemented.
Origin: operator backlog item "Plan 4 — #8 Dolby Vision RPU / HDR10+ dynamic metadata"
(Effort XL, AGENTS.md §7 risk: FFmpeg command generation, publish behavior,
settings schema, plus new external tooling).

Goal: preserve Dolby Vision (DoVi) RPU and/or HDR10+ (SMPTE ST 2094-40) dynamic
metadata across the pipeline instead of silently flattening to static HDR10 on
the encode route (today's verified behavior). Ship detection + honest warnings
first; treat full preservation as a gated, phased epic.

Every phase below is a SEPARATE session with its own operator approval,
docs/SESSION.md scope block, change packet under `ops/release/changes/unreleased/`,
and validation rung. Do not combine phases into one session.

---

## 0. Execution ground rules (Codex: read before any edit)

1. Follow AGENTS.md startup (§4.1). Read this plan, then docs/SESSION.md, then the
   exact source files named per phase. PROJECT_INDEX.md and docs/audit/latest.md
   were absent on 2026-06-11 (degraded mode); ask the operator before regenerating.
2. This work touches AGENTS.md §7 rows: "FFmpeg command generation and stream
   mapping", "Source/scratch/output file movement" (temp artifacts), "Settings
   schema/defaults/persistence" (Phase 2+ config keys). Per AGENTS.md §5 the rung
   is "Release gate plus real-media validation". Do NOT self-certify §7; agent-side
   tests run, operator runs the real-media rung.
3. Never commit, never push, never create branches unless the operator asks.
   No emojis anywhere. ISO dates in saved notes.
4. Create/update a change packet (`MP-CHANGE-2026-XXXX-NNN.json`) per session via
   `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py
   mediapipeline.tools.change_control.record_change_touch`, and run
   `... mediapipeline.tools.change_control.validate_changes --require-worktree-coverage`
   before the final response.
5. After edits, regenerate summaries:
   `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py
   mediapipeline.tools.dev.refresh_summaries --paths <each edited file>`.
6. Ollama (project CLAUDE.md §4): NOT allowed for any code in this plan (it is §7
   and multi-file). Permitted only for prose drafts (e.g. README text in §5.1).
7. Source media is read-only. All new intermediate artifacts (RPU bin, HDR10+
   JSON, extracted HEVC) go in `$script:processingDir` (scratch), named with the
   `encode_temp_`/`temp_` GUID style so the existing stale-partial sweep and
   `ops/pipeline/engine/shared/temp_cleanup.ps1` conventions apply. Never write
   them next to the source or the published output.

### 0.1 Repo-specific traps (each has burned a prior session — do not rediscover)

- T1 — `exit` inside a dot-sourced entrypoint slice does NOT exit the pipeline.
  Any fatal path added under `ops/pipeline/entrypoints/MediaPipeline/*.ps1` must
  use the `$startupFatalExitCode` sentinel contract (see docs/SESSION.md
  "Handoff 2026-06-10"). Runtime failures inside `Do-Encode`/`Do-Remux` use
  `return $false` + `Register-SourceFailure`, never `exit`.
- T2 — New engine modules must be registered. `ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1`
  holds `$engineModuleLoadOrder` plus a startup contract check that the load order
  and the module manifest describe the same module set (46 modules as of
  2026-06-10; FATAL on drift). Adding `ops/pipeline/engine/**/*.ps1` means updating
  BOTH lists in the same commit, and the count assertion if one exists.
- T3 — Config keys are registered in lockstep across at least:
  `ops/pipeline/engine/config/config_keys.ps1` (registry),
  `ops/pipeline/engine/config/config_schema.ps1` (ordered keys),
  `ops/pipeline/engine/config/default_values.ps1`,
  `ops/pipeline/config/schemas/media_pipeline_config.schema.json`,
  `ops/pipeline/config/MediaPipeline_config_template.psd1`,
  `ops/pipeline/config/profiles/Default.psd1`,
  Python `app/kernel/config_keys.py` (KEY_* constants).
  `ops/pipeline/tests/Unit/Invoke-ConfigKeyRegistryChecks.ps1` enforces count and
  ORDER alignment — keys must be inserted at the same ordinal position everywhere.
- T4 — `-x265-params` is colon-separated. A Windows absolute path
  (`C:\...`) inside file-valued x265 params such as `dhdr10-info=` breaks x265
  param parsing on the drive colon. See §6.3 for the mandated mitigation; never
  pass a raw absolute Windows path inside `-x265-params`. The validated FFmpeg
  Dolby Vision encode path uses native `-dolbyvision true`, not
  `dolby-vision-rpu=` inside `-x265-params`.
- T5 — NVENC cannot carry a DoVi RPU or write per-frame ST 2094-40 SEI. DoVi/HDR10+
  preservation params must only ever be appended on the CPU/libx265 branch of
  `New-EncodeVideoFlags`. The GPU primary and safe-retry attempts must be skipped
  entirely when preservation is required (§6.4).
- T6 — Sidecar JSON serializes with `-Depth 10`
  (`ops/pipeline/engine/publish/sidecar.ps1:195`). Keep the new evidence block
  within 3 levels of nesting.
- T7 — The new tools must NOT be startup-fatal. ffmpeg/ffprobe/mkvmerge absence is
  FATAL at `ops/pipeline/entrypoints/MediaPipeline.ps1:278-281`; dovi_tool /
  hdr10plus_tool absence only disables preservation (policy falls back per §4.2)
  with a logged WARN. A regression check asserts the existing FATAL wording —
  do not copy that pattern for the new tools.
- T8 — "Fail-to-pending" in the backlog text does NOT mean the pending-publish
  park/drain flow (that is reserved for unsafe final roots, AGENTS.md §3.3).
  The policy-failure mechanism is `Register-SourceFailure`
  (`ops/pipeline/engine/failures/failure_state.ps1:635`) with
  `-Classification 'operator_required'`, which routes the file to review and
  blocks silent publish.
- T9 — Do not bump `$script:PipelineVersion` / `MinPipelineVersion`.
  `Test-OutputNeedsReprocess` (`ops/pipeline/engine/publish/sidecar.ps1:329`)
  would mark the whole existing library stale and trigger mass reprocessing.
  Whether DoVi titles should be re-encoded after Phase 3 ships is an operator
  decision (decision log D8), not a version bump.
- T10 — `Get-HDRState` semantics are load-bearing (encode aborts on
  `Known=$false`, `ops/pipeline/entrypoints/MediaPipeline/encode.ps1:49-58`). Do
  not modify it. All new detection is additive in new functions.
- T11 — Do not change `source_media_profile.v1`
  (`ops/pipeline/engine/probe/media_probe.ps1:412`, consumed by
  `ops/pipeline/engine/process/pipeline_processing.ps1:365`,
  `ops/pipeline/engine/queue/snapshot_rows.ps1:273`, route plan, sidecar, and
  Python readers). Dynamic-HDR facts travel in their own new structure (§5.4 /
  Appendix B), not by mutating that schema.

---

## 1. Current behavior (verified 2026-06-11, with citations)

- HDR detection is transfer-function only: `Get-HDRState`
  ([media_probe.ps1:250](../../ops/pipeline/engine/probe/media_probe.ps1)) marks
  `smpte2084`/`arib-std-b67` as HDR. DoVi and HDR10+ are invisible to it (the
  comment at lines 245-249 says DoVi is "implicitly handled" — true for the
  static-HDR10 base only).
- Static HDR10 mastering metadata IS preserved on CPU encode:
  `Get-SourceHdr10MasteringMetadata` (media_probe.ps1:285) probes frame 1
  side data; `Do-Encode` calls it once
  ([encode.ps1:67](../../ops/pipeline/entrypoints/MediaPipeline/encode.ps1)) and
  threads `-Hdr10MasterDisplay`/`-Hdr10MaxCll` into every `New-EncodeAttemptPlan`
  call (encode.ps1:165, 215, 297). `New-EncodeVideoFlags`
  ([encode_policy.ps1:197-231](../../ops/pipeline/engine/decide/encode_policy.ps1))
  emits `hdr10=1:hdr10-opt=1:repeat-headers=1:master-display=...:max-cll=...` in
  `-x265-params` on the CPU branch.
- Dynamic metadata is silently dropped on every encode: hevc_nvenc carries
  neither RPU nor ST 2094-40; libx265 receives no RPU and (without explicit
  flags/side-data passthrough) no HDR10+ metadata. No log line, no sidecar
  field, no event records this loss. That is the gap Phase 1 closes.
- The remux route copies all real video streams (`-map 0:V -c:v copy`,
  [remux.ps1:178](../../ops/pipeline/entrypoints/MediaPipeline/remux.ps1)) into a
  temp MKV via ffmpeg, then muxes final output with mkvmerge (remux.ps1:268+).
  In-band RPU/SEI NAL units survive stream copy, so remux output most likely
  still carries DoVi/HDR10+ — but the container-level DoVi configuration record
  (`dvcC`/`dvvC` block-addition mapping) passing through the ffmpeg temp_av leg
  is UNVERIFIED for the bundled ffmpeg build. Phase 2 must verify this (§5.4);
  if the record is lost, players will not engage DoVi even with RPUs present.
- Encode attempts ladder: GPU primary, GPU safe retry, CPU fallback
  (encode.ps1:144-330), with the NVENC availability cache
  (`Test-NvencAvailable` / `Test-NvencProbeReportsAvailable` /
  `Invalidate-NvencAvailableProbe`, encode_policy.ps1:484-656) able to force the
  CPU path via `$skipGpuDueToProbe` (encode.ps1:150). CPU encodes re-check
  scratch space with `-IsCpuEncode` (encode.ps1:291) and serialize machine-wide
  via `Acquire-CpuEncodeMutex` (encode.ps1:329).
- Route selection: `Resolve-InitialMediaRoutePlan`
  ([routing.ps1:314](../../ops/pipeline/engine/decide/routing.ps1)) →
  `Resolve-MediaRouteBySize`; remux additionally gates by codec via
  `Resolve-RemuxCodecRoutePlan` (remux.ps1:73, decide/codec_policy.ps1) and can
  hand off to `Do-Encode` mid-flight (remux.ps1:94) with the scratch copy left in
  place (`$localIn = $null` suppresses cleanup). The reverse handoff
  (encode → remux on oversized output) also exists (`FallbackFromOversizedEncode`,
  remux.ps1:75/96-123).
- Completion evidence: `$sidecarExtra`
  ([publish_completion.ps1:167-210](../../ops/pipeline/engine/publish/publish_completion.ps1))
  is merged into the sidecar payload by `Write-Sidecar` (sidecar.ps1:165,
  `pipeline_sidecar.v1`) and mirrored to the completed-jobs manifest
  (`Add-CompletedJobsManifestEntry`, sidecar.ps1:268, `completed_job.v1`).
  Python completed/manifest readers pass payload fields through generically, so
  ADDITIVE sidecar fields need no Python contract change.
- Output verification today: `Test-DurationMatch` after encode (encode.ps1:454)
  and remux (remux.ps1:402); `Invoke-MediaVerificationSafetyChecks.ps1` unit-tests
  its fail-closed behavior. There is no `ops/pipeline/engine/verify/` directory;
  verification helpers live in `probe/media_probe.ps1`.
- Tool resolution: `Resolve-BundledExecutable`
  ([executable_resolution.ps1:11](../../ops/pipeline/engine/shared/executable_resolution.ps1))
  with relative candidates rooted at `$scriptDir`; wired at
  MediaPipeline.ps1:278-295. Bundled tools live under `ops/pipeline/tools/<Tool>/`
  (ffmpeg, MKVToolNix, PgsToSrt, SubtitleEdit), with `README_ffmpeg_here.txt`
  as the placeholder pattern for binaries not tracked by git.

---

## 2. Policy model (the contract all phases implement)

One new config key (added in Phase 2, NOT Phase 1):

`DynamicHdrPolicy` — string enum:

| Value | Meaning |
| --- | --- |
| `warn` (default) | Detect DoVi/HDR10+; never change routing or commands; record honest evidence + WARN when metadata will be / was dropped. Phase 1 behavior, permanent fallback. |
| `preserve_or_remux` | Preserve where supported (§2.1); where unsupported on the chosen route, force the remux route when codec-safe; if remux is also blocked, drop with warning evidence (never fail the file). |
| `preserve_or_review` | Preserve where supported; where unsupported, `Register-SourceFailure -Classification 'operator_required'` (file goes to review; no output published). |
| `off` | Skip the new probes entirely (zero added ffprobe cost); behavior identical to pre-plan pipeline. |

Two support keys: `DoviToolPath` and `Hdr10PlusToolPath` (string, default `''` =
use bundled; same pattern as `BdpgsOcrToolPath`).

### 2.1 Per-profile support matrix (what "preserve" means)

| Source metadata | Remux route | Encode route (policy `preserve_*`) |
| --- | --- | --- |
| DoVi profile 8.1 (BL compat id 1, HDR10 base) | Pass through; verify (Phase 2/4) | x265 CPU only, FFmpeg native `-dolbyvision true` + `dolby-vision-profile=8.1`/VBV x265 params; extracted RPU is retained as roundtrip evidence (Phase 3) |
| DoVi profile 7 (UHD-BD dual layer) | Pass through as-is; verify | Convert RPU 7→8.1 via `dovi_tool -m 2 extract-rpu`; encode BL with converted RPU; EL is intentionally discarded (Phase 3) |
| DoVi profile 5 (IPTPQc2, no HDR10 base) | Pass through; verify | NOT preservable by encode (no compatible base layer). `preserve_or_remux` → remux; `preserve_or_review` → review. Never re-encode P5 video. |
| DoVi profile 4 / 8.2 / 8.4 / anything else | Pass through; verify | Treated as unsupported-for-encode, same handling as profile 5 |
| HDR10+ only | Pass through; verify | x265 CPU only, `dhdr10-info=<json>` (Phase 3) |
| DoVi + HDR10+ both | Pass through; verify | Apply both mechanisms when DoVi profile is encode-supported; otherwise unsupported path wins |
| Neither | No change to any behavior | No change to any behavior |

SDR sources (`Get-HDRState.IsHDR=$false`): probes are skipped, everything
unchanged. Output container gate: preservation requires `OutputContainer = 'mkv'`
(the default, `ops/pipeline/engine/config/default_values.ps1:247`). If the
operator configures `mp4`, preservation is treated as unsupported-for-encode
(MP4 DoVi needs `dvh1`/`dvvC` boxes the current mux chain does not produce).

---

## 3. Phase sequence overview

| Phase | Ships | New config keys | New tools | §7 surface |
| --- | --- | --- | --- | --- |
| 1 — Detect + warn | Probe functions, evidence on sidecar/completed record, WARN log + pipeline event | none | none | Probe + sidecar Extra only (additive) |
| 2 — Tools + remux verification | Bundled dovi_tool/hdr10plus_tool, resolution wiring, capability probes, verify-on-remux, `DynamicHdrPolicy` key | 3 keys | 2 binaries | Settings schema; remux verify gate |
| 3 — Preserve on encode | Pure preserve/remux/review planner is implemented; RPU/JSON extract, x265 param injection, CPU forcing, and route gating remain open | none | none | FFmpeg command generation (highest risk) |
| 4 — Output verification gate | Round-trip verification before publish on both routes | none | none | Publish gating |

Phase 1 is independently valuable and must ship even if 2-4 are never approved.
Do not start a phase until the previous phase's operator validation is recorded
in docs/SESSION.md.

---

## 4. Phase 1 — Detection + honesty (small, self-contained)

### 4.1 Files

EDIT `ops/pipeline/engine/probe/media_probe.ps1` — add two functions (below).
EDIT `ops/pipeline/entrypoints/MediaPipeline/encode.ps1` — probe + warn + stash evidence.
EDIT `ops/pipeline/entrypoints/MediaPipeline/remux.ps1` — probe + stash evidence.
EDIT `ops/pipeline/engine/publish/publish_completion.ps1` — add evidence to `$sidecarExtra`.
NEW  `ops/pipeline/tests/Unit/Invoke-DynamicHdrDetectionChecks.ps1`.
Plus summaries for each, change packet, docs/SESSION.md scope block.

No new module file in Phase 1 (avoids trap T2). No config keys (avoids T3).

### 4.2 New function: `Get-DolbyVisionState`

Location: media_probe.ps1, directly after `Get-SourceHdr10MasteringMetadata`
(ends near line 400). House style: `[pscustomobject][ordered]@{}` results,
`Invoke-FFprobeCommand` wrapper, explicit `Known/Reason` failure shape exactly
like `Get-HDRState`.

```powershell
function Get-DolbyVisionState {
    param([string]$FilePath)
    # ffprobe -v error -select_streams v:0
    #   -show_entries stream=codec_name:stream_side_data_list -of json -- <file>
    # via Invoke-FFprobeCommand -TimeoutSeconds 30 -Stage 'dovi-detection'
}
```

Return shape (all fields always present):

```text
Known            [bool]   probe ran and parsed
Reason           [string] populated when not Known
DoviPresent      [bool]   a side_data entry of type matching '(?i)dovi configuration'
DoviProfile      [int]    dv_profile (0 when absent)
DoviLevel        [int]    dv_level (0 when absent)
DoviBlCompatId   [int]    dv_bl_signal_compatibility_id (-1 when absent)
DoviRpuPresent   [bool]   rpu_present_flag -eq 1
DoviElPresent    [bool]   el_present_flag -eq 1
```

Implementation notes:
- The side data entry type string and field names (`dv_profile`, `dv_level`,
  `rpu_present_flag`, `el_present_flag`, `bl_present_flag`,
  `dv_bl_signal_compatibility_id`) must be confirmed against the BUNDLED ffprobe
  (`ops\pipeline\tools\ffmpeg\bin\ffprobe.exe`) on a real DoVi sample before the
  regexes are finalized. Do not trust this plan's spelling blindly; ffprobe
  versions have varied the casing of "DOVI configuration record".
- Probe failure (nonzero exit, timeout, JSON parse error) → `Known=$false` with
  reason, like `Get-HDRState`. Callers treat unknown as "no DoVi" but record the
  reason in evidence; Phase 1 must NOT abort processing on this probe (unlike
  `Get-HDRState`, which stays the only fatal HDR gate).
- A missing `side_data_list` is the normal non-DoVi case: `Known=$true,
  DoviPresent=$false`.

### 4.3 New function: `Test-Hdr10PlusPresence`

Same location, after `Get-DolbyVisionState`.

```powershell
function Test-Hdr10PlusPresence {
    param([string]$FilePath, [int]$FrameSampleCount = 24)
    # ffprobe -v error -select_streams v:0 -read_intervals "%+#24"
    #   -show_frames -show_entries frame=side_data_list -of json -- <file>
    # via Invoke-FFprobeCommand -TimeoutSeconds 60 -Stage 'hdr10plus-detection'
}
```

Return shape: `Known [bool]`, `Reason [string]`, `Hdr10PlusPresent [bool]`,
`SampledFrames [int]`.

- Present when ANY sampled frame has a `side_data_list` entry whose
  `side_data_type` matches `(?i)SMPTE.?2094|HDR.?10\+|HDR Dynamic Metadata`.
  Confirm the exact string against the bundled ffprobe on a real HDR10+ sample
  (commonly `HDR Dynamic Metadata SMPTE2094-40 (HDR10+)`).
- 24 frames (~1 GOP) bounds cost; HDR10+ SEI is per-frame in practice so frame 1
  usually suffices, but trailers/intros without metadata are why we sample more
  than one. 60 s timeout because decoding 24 UHD frames off SMB can be slow —
  but note the probe runs against the SCRATCH copy (local disk), see §4.4.

### 4.4 `Do-Encode` integration (encode.ps1)

Insertion point: immediately after the existing `Get-SourceHdr10MasteringMetadata`
block (after line 75), before `$usingCpu = $false` (line 76). Only when
`$isHDR` is true:

```powershell
$script:CurrentDynamicHdrEvidence = $null
if ($isHDR) {
    $doviState  = Get-DolbyVisionState -FilePath $localIn
    $hdr10pState = Test-Hdr10PlusPresence -FilePath $localIn
    $script:CurrentDynamicHdrEvidence = New-DynamicHdrEvidence `   # small builder, see below
        -Route 'encode' -DoviState $doviState -Hdr10PlusState $hdr10pState
    if ($script:CurrentDynamicHdrEvidence.dynamic_metadata_present) {
        Write-Log ("ENCODE: source carries dynamic HDR metadata (" +
            $script:CurrentDynamicHdrEvidence.summary +
            ") - it will be DROPPED by this encode (static HDR10 only)") "WARN"
        Write-PipelineEvent -EventType 'dynamic_hdr_metadata_dropped' -Stage 'encode_prepare' `
            -Route 'encode' -Status 'warn' -SourcePath $file.FullName -Data @{
                dovi_present      = ...; dovi_profile = ...
                hdr10plus_present = ...
            } | Out-Null
    }
}
```

- `New-DynamicHdrEvidence` is a tiny pure helper in media_probe.ps1 that folds
  the two states into the Appendix B ordered hashtable, computing
  `outcome = 'will_drop_encode' | 'expected_preserved_remux' | 'none_detected' |
  'probe_failed'` and a one-line `summary` like `"DoVi profile 7 (EL present) + HDR10+"`.
- Probe failures must not fail the file in Phase 1: evidence records
  `probed=false` + reason; no `Register-SourceFailure`, no `throw`. This is the
  opposite of the `Get-HDRState` contract on purpose — Phase 1 adds zero new
  failure modes.
- `$script:CurrentDynamicHdrEvidence` must be reset to `$null` at the top of both
  `Do-Encode` and `Do-Remux` (next to `$script:CurrentEncodeAttempts = @()`,
  encode.ps1:16) so a probe-skipped file never inherits the previous file's
  evidence. This mirrors how `$script:CurrentEncodeAttempts` and
  `$script:LastPublishResult` are handled.

### 4.5 `Do-Remux` integration (remux.ps1)

Same pattern. Insertion point: after `Resolve-RemuxCodecRoutePlan` commits the
remux route (after remux.ps1:126, before `Set-ProgressStage -Stage 'remux_prepare'`
at 128). Gate the probes on the route plan's HDR flag
(`$script:CurrentRoutePlan` source profile `is_hdr`, falling back to
`Get-HDRState $localIn` only if absent — do NOT make remux fail on HDR-unknown,
that is not its current behavior). Route value `'remux'`, outcome
`'expected_preserved_remux'` when metadata present, and the log line is INFO not
WARN ("dynamic HDR metadata expected to pass through remux; verification ships
in a later phase").

Watch the remux→encode handoff at remux.ps1:94: `Do-Encode` re-runs its own
probes, so evidence set by `Do-Remux` before the handoff is overwritten by the
encode-side reset — that is correct; verify it in the unit test. Same for the
encode→remux oversized fallback: `Do-Remux` re-probes and overwrites.

### 4.6 Sidecar evidence (publish_completion.ps1)

After the `$sidecarExtra['folder_policy']` line (publish_completion.ps1:205),
add:

```powershell
if ($script:CurrentDynamicHdrEvidence) {
    $sidecarExtra['dynamic_hdr'] = $script:CurrentDynamicHdrEvidence
}
```

Also check `ops/pipeline/engine/publish/publish_partial.ps1` and the parked-push
path (`pending_push.ps1` / `pending_drain_transaction.ps1:229`): the drain-side
sidecar is rebuilt from the park manifest. In Phase 1 it is ACCEPTABLE for
parked-then-drained outputs to lack `dynamic_hdr` (document this in the change
packet); wiring evidence through the park manifest is Phase 4 work. Confirm the
drain path does not crash on the new key being absent (it cannot, additive), and
grep for any sidecar schema JSON (`pipeline_sidecar`) under
`ops/pipeline/config/schemas/`; if one exists, add the optional `dynamic_hdr`
property and run `ops/pipeline/tests/Unit/Invoke-ContractSchemaChecks.ps1`.

The Python completed-record path (`app/completed/manifest.py` etc.) passes
unknown payload fields through; NO Python edits in Phase 1. Surfacing a
"DV/HDR10+ dropped" chip in the WebView completed drawer is an optional
follow-up for a separate UI session — name it in the handoff, do not do it.

### 4.7 Phase 1 tests and validation

NEW `ops/pipeline/tests/Unit/Invoke-DynamicHdrDetectionChecks.ps1`, modeled on
`Invoke-MediaVerificationSafetyChecks.ps1` (stub `Invoke-FFprobeCommand`, feed
canned JSON):
1. DoVi P7 JSON (dv_profile=7, el_present_flag=1) → DoviPresent, profile 7, EL true.
2. DoVi P8 JSON (dv_profile=8, compat id 1) → profile 8, compat 1.
3. No side data → Known=true, DoviPresent=false.
4. ffprobe exit 1 → Known=false with reason; evidence builder yields
   `probed=false`, outcome `probe_failed`, and (critically) Do-Encode-style
   caller logic does not throw.
5. HDR10+ frame JSON with `HDR Dynamic Metadata SMPTE2094-40` on frame 3 of 24
   → present.
6. Evidence builder: encode route + DoVi → `will_drop_encode` + warning text;
   remux route + HDR10+ → `expected_preserved_remux`; SDR/absent → `none_detected`.

Agent-side validation: parse-check every edited file
(`[System.Management.Automation.Language.Parser]::ParseFile`), run the new unit
check, `ops/pipeline/tests/Invoke-EndToEndSmokeChecks.ps1` (must stay exit 0; its
fixtures are SDR so the new code paths must be inert there), and
`Invoke-ContractSchemaChecks.ps1` if a sidecar schema was touched.

Operator validation (record as REQUIRED, not self-certified): one real `-Once`
run over (a) one DoVi UHD remux source, (b) one HDR10+ source, (c) one plain
HDR10 source; confirm the WARN line, the `dynamic_hdr_metadata_dropped` event in
the events feed, and the `dynamic_hdr` block in the output sidecar +
completed-jobs manifest entry.

### 4.8 Phase 1 acceptance criteria

- Encoding a DoVi or HDR10+ source produces: WARN log line, warn pipeline event,
  `dynamic_hdr` sidecar block with `outcome=will_drop_encode`.
- Remuxing one produces evidence with `outcome=expected_preserved_remux`, INFO log.
- SDR and metadata-free HDR10 files: zero behavioral diff (no extra probes for
  SDR; for HDR10-only, two extra bounded ffprobe calls and
  `outcome=none_detected`).
- Probe failure degrades to evidence-with-reason; the file still processes
  exactly as before.
- End-to-end smoke green; no new config keys; no module-count change.

---

## 5. Phase 2 — Bundle tools, wire resolution, verify the remux path

### 5.1 Tool bundling

NEW directories following the existing pattern:

```text
ops/pipeline/tools/dovi_tool/dovi_tool.exe          (binary, expected gitignored)
ops/pipeline/tools/dovi_tool/README_dovi_tool_here.txt
ops/pipeline/tools/hdr10plus_tool/hdr10plus_tool.exe
ops/pipeline/tools/hdr10plus_tool/README_hdr10plus_tool_here.txt
```

- Run `git check-ignore -v ops/pipeline/tools/ffmpeg/bin/ffmpeg.exe` first to
  learn how binaries are excluded; mirror that for the two new dirs (extend
  `.gitignore` only if the existing rule does not already cover them — show the
  operator the diff).
- READMEs must record: upstream project (`quietvoid/dovi_tool`,
  `quietvoid/hdr10plus_tool` on GitHub), exact pinned release version, download
  URL, SHA-256 of the bundled exe, license (both MIT — bundling is permitted;
  copy the upstream LICENSE file into the tool dir), and the one-line purpose.
- The OPERATOR downloads/places the binaries (agent sessions must not download
  executables without explicit approval). Pin: dovi_tool >= 2.1.x,
  hdr10plus_tool >= 1.6.x; record the exact chosen versions in the README and
  the change packet.

### 5.2 Resolution wiring

EDIT `ops/pipeline/entrypoints/MediaPipeline.ps1` directly under line 281
(mkvextract):

```powershell
$doviToolPath      = Resolve-BundledExecutable -CommandName 'dovi_tool'      -RelativeCandidates @('..\tools\dovi_tool\dovi_tool.exe', 'Tools\dovi_tool\dovi_tool.exe')
$hdr10plusToolPath = Resolve-BundledExecutable -CommandName 'hdr10plus_tool' -RelativeCandidates @('..\tools\hdr10plus_tool\hdr10plus_tool.exe', 'Tools\hdr10plus_tool\hdr10plus_tool.exe')
```

- Config overrides win: if `DoviToolPath`/`Hdr10PlusToolPath` (new keys, §5.5)
  are non-empty and exist, use them instead. Follow whatever precedence pattern
  `BdpgsOcrToolPath` uses (grep its consumption before writing this).
- NOT fatal when null (trap T7). Log one startup INFO per missing tool stating
  preservation is unavailable and which policy fallback applies.
- Expose as `$script:DoviToolPath` / `$script:Hdr10PlusToolPath` for engine
  modules (match how `$ffprobePath` reaches media_probe.ps1 — see its header
  comment, media_probe.ps1:9).

### 5.3 Capability probes (new module)

NEW `ops/pipeline/engine/process/dynamic_hdr.ps1` — register in
`module_loader.ps1` load order AND manifest (trap T2; count goes 46→47 if the
contract enumerates a count). This module owns everything tool-shaped:

- `Test-DynamicHdrToolsAvailable` — returns
  `[pscustomobject] @{ DoviTool=[bool]; DoviToolVersion=[string]; Hdr10PlusTool=[bool]; Hdr10PlusToolVersion=[string]; Reason=[string] }`
  by running `<tool> --version` with a 10 s timeout through the native-process
  wrapper used elsewhere (`ops/pipeline/engine/shared/native.ps1` /
  `native_process_contracts.ps1` — reuse `Invoke-FFprobeCommand`'s underlying
  runner pattern; do NOT shell out bare).
- `Test-X265DynamicHdrCapability` — cached one-shot probe in the style of
  `Test-NvencAvailable` (encode_policy.ps1:484): inspect
  `ffmpeg -h encoder=libx265` for native `-dolbyvision` support, and separately
  run a one-frame lavfi encode with relative `dhdr10-info=<tiny json>` to prove
  HDR10+ x265 support when a JSON fixture is available. Cache in
  `$script:DynamicHdrCapabilityProbe` for process lifetime. The probe is only
  invoked lazily on the first file that wants preservation (never at startup —
  startup cost is a §7-adjacent regression).

### 5.4 Remux-path verification (the real deliverable of Phase 2)

Question to answer with evidence, then encode the answer in code: does
`source.mkv → ffmpeg (-map 0:V -c copy) temp_av.mkv → mkvmerge final.mkv`
preserve (a) in-band RPUs, (b) the container DoVi configuration record,
(c) HDR10+ SEI?

Procedure (agent-runnable with fixture media, no library writes):
1. `ffprobe -show_entries stream=codec_name:stream_side_data_list` on source,
   temp_av, final — compare DOVI configuration records.
2. `dovi_tool extract-rpu` on HEVC extracted from final
   (`mkvextract tracks final.mkv 0:video.hevc`, `$mkvextractPath` is already
   wired) — RPU count equals source's.
3. `hdr10plus_tool extract` on the same — JSON non-empty for HDR10+ sources.

Outcomes:
- If everything passes: no remux flow change. Add
  `Test-DynamicHdrOutputIntegrity` (in `dynamic_hdr.ps1`; spec in §7.1) and call
  it after `Test-DurationMatch` (remux.ps1:402) only when evidence says metadata
  present AND policy != off/warn — wired now but enforcement semantics per §7.
- If the ffmpeg temp_av leg drops the DoVi config record: STOP. Report findings;
  the candidate fixes (mkvmerge directly from source for DoVi files, ffmpeg
  upgrade, or post-mux record restoration) each touch §7 remux flow and need an
  operator decision (decision log D5). Do not improvise a fix in the same session.

### 5.5 Config keys (single settings-schema touch for the whole epic)

Add `DynamicHdrPolicy` (enum: off|warn|preserve_or_remux|preserve_or_review,
default `warn`), `DoviToolPath` (string ''), `Hdr10PlusToolPath` (string '') —
all 7 surfaces from trap T3, same ordinal position in each, enum registered in
the choice registry (`ops/pipeline/engine/config/choice_registry.ps1`) so the
settings UI can render a dropdown. Then:
- `Invoke-ConfigKeyRegistryChecks.ps1` green (key count rises by 3).
- `ops/pipeline/tests/Unit/Invoke-RuntimeConfigResolutionChecks.ps1` — note it
  currently self-skips on a stale path (docs/SESSION.md 2026-06-10, "Pre-existing,
  not mine"); do not "fix" it silently — flag to operator.
- Python settings tests under `tests/python/desktop/` that enumerate config keys
  (grep `test_config_keys`) — update expected counts/lists.
- Settings UI exposure (Video tab) is OPTIONAL and a separate session; the key
  works via direct PSD1 edit until then. Say so in the handoff.

### 5.6 Phase 2 tests and validation

- NEW `ops/pipeline/tests/Unit/Invoke-DynamicHdrToolingChecks.ps1`: resolution
  precedence (config override > bundled > AllowSystemTools), missing-tool
  non-fatal behavior, capability-probe caching, version parsing.
- Re-run Phase 1 unit checks; `Invoke-ConfigKeyRegistryChecks.ps1`;
  end-to-end smoke; `-ValidateOnly` run; `-DumpEffectiveConfigPath` parity
  EXCEPT the three new keys (list them as the only expected diff).
- Operator: real DoVi P7 + P8.1 + HDR10+ remuxes with the §5.4 procedure
  results attached to the worksheet
  (`ops\scripts\operator\New-RealMediaValidationWorksheet.ps1`).

Acceptance: tools resolve and version-report; capability probe returns a stable
answer on this machine; remux verification verdict documented with evidence;
config keys live and registry checks green; `warn` default means zero behavior
change for existing users.

---

## 6. Phase 3 — Preserve on encode (x265 CPU path only)

The §7-heaviest phase. Pre-condition: Phase 2 verdict says remux preserves, and
the capability probe says the bundled FFmpeg/libx265 exposes native
`-dolbyvision` for Dolby Vision coding and `dhdr10-info` for HDR10+ when an
HDR10+ fixture is available. If the required feature is false, this phase is
BLOCKED — report, do not work around.

### 6.1 Decision gating in `Do-Encode`

Status 2026-06-21: `Resolve-DynamicHdrEncodePreservationDecision` now folds the
existing evidence object, configured policy, MKV-only output guard, tool
availability, and x265 capability evidence into a side-effect-free decision
object. It identifies warn/off/no-op cases, unsupported containers,
`preserve_or_remux` remux preference, `preserve_or_review` hold-review cases,
and the CPU/libx265 `preserve_encode` path with `should_extract`,
`should_force_cpu`, and `should_attempt_gpu=false`. `Do-Encode` does not consume
this decision yet; route changes, extraction invocation, and x265 artifact
injection remain open.

After the Phase 1 evidence block (post encode.ps1:75), when policy is
`preserve_or_remux`/`preserve_or_review` and evidence shows dynamic metadata:

1. Compute `$preservePlan` via the pure function
   `New-DynamicHdrPreservationPlan` in `ops/pipeline/engine/process/dynamic_hdr.ps1`.
   It takes route, policy, DoVi profile/compat/EL, HDR10+ flag, tool availability,
   x265 capability, codec, and CPU-fallback posture. It returns an ordered
   `dynamic_hdr_preservation_plan.v1` object with `action`, `recommended_route`,
   `can_preserve_encode`, `target_dovi_profile`, `required_artifacts`, `caveats`,
   and `reasons`. It performs no I/O and does not change routing or FFmpeg
   arguments by itself; the support matrix in §2.1 is its truth table.
2. `Action='force_remux'`: log decision, set
   `$script:CurrentRouteReasonCode='dynamic_hdr_force_remux'` and reason text,
   then hand off exactly like the codec fallback does in reverse — mirror
   remux.ps1:74-94: leave scratch in place (`$localIn = $null`) and
   `return Do-Remux $file $isTV $tvInfo`. VERIFY first that `Do-Remux` tolerates
   entry with the route plan currently saying encode (the codec route plan is
   recomputed inside Do-Remux at line 73, so it should; prove it in the smoke).
   Guard against ping-pong: `Do-Remux` can bounce back to `Do-Encode` only via
   the codec gate, and DoVi sources are HEVC (remux-safe), so a loop cannot
   occur — assert this reasoning in a unit test with an h264+fake-DoVi input
   (expected: codec gate wins, returns to encode, preservation then resolves to
   review/drop because remux was refused; the decision trace must show both).
3. `Action='review'`: `Register-SourceFailure -Classification 'operator_required'
   -Stage 'dynamic-hdr-policy' -ErrorCode 'DYNAMIC_HDR_UNPRESERVABLE'`
   with a SuggestedAction explaining which profile/tool/capability was the
   blocker; `return $false`.
4. `Action='drop_warn'`: Phase 1 behavior (warn + evidence), continue unchanged.
5. `Action='encode_preserve'`: continue to §6.2.

### 6.2 Metadata extraction (in `dynamic_hdr.ps1`)

Status 2026-06-21: `New-DynamicHdrMetadataExtractionPlan` builds a fail-closed
command topology for HEVC stream extraction, Dolby Vision RPU extraction/summary,
and HDR10+ JSON extraction. It requires explicit MKV video track IDs instead of
assuming track `0`, chooses ffmpeg Annex-B extraction for non-MKV inputs, and
records temp artifact paths for the existing cleanup flow.
`Export-DynamicHdrMetadata` can execute that plan through the shared native
runner, records per-command results, verifies non-empty HEVC/RPU/HDR10+ temp
artifacts, persists RPU summary evidence, and parses a positive RPU frame count.
The executor is not wired into `Do-Encode` yet and does not alter routing.
Encode-route injection wiring, output verification, policy fallback after tool
failure, and real-media validation remain open.

`Export-DynamicHdrMetadata -ScratchPath $localIn -Evidence $evidence -WorkDir $script:processingDir`
returns `RpuPath`, `Hdr10PlusJsonPath`, `RpuFrameCount`, `Ok`, `Reason`,
`ErrorCode`. Steps (all temp files GUID-named in `$script:processingDir`,
removed in the existing finally/cleanup flow of Do-Encode — extend the cleanup
list, do not add a second cleanup mechanism):

1. Extract HEVC elementary stream:
   `& $mkvextractPath tracks "$localIn" "0:$workHevc"` for MKV sources; for
   MP4/TS sources use
   `ffmpeg -i in -map 0:v:0 -c:v copy -bsf:v hevc_mp4toannexb -f hevc $workHevc`.
   (Track id 0 is an assumption — derive the video track id from the existing
   ffprobe stream index, do not hardcode.)
2. DoVi P8.1: `& $doviToolPath extract-rpu -i $workHevc -o $rpuBin`.
   DoVi P7: `& $doviToolPath -m 2 extract-rpu -i $workHevc -o $rpuBin`
   (mode 2 = convert to 8.1, discards EL mapping).
3. `& $doviToolPath info -i $rpuBin --summary` (or `-f` per pinned version's
   CLI) to capture RPU frame count for §7 verification.
4. HDR10+: `& $hdr10plusToolPath extract -i $workHevc -o $hdr10plusJson`;
   non-empty JSON required.
5. Any nonzero exit / empty artifact → `Ok=$false` with `ErrorCode` in
   {`DOVI_RPU_EXTRACT_FAILED`,`HDR10PLUS_EXTRACT_FAILED`,`DYNAMIC_HDR_TOOL_MISSING`};
   caller maps to `review` (preserve_or_review) or `force_remux`
   (preserve_or_remux) — extraction failure must NEVER silently fall back to a
   plain dropping encode.

Disk note: the extracted HEVC is ~source-video-size; extend the existing
`Test-EstimatedOutputSpace` preflight call in Do-Encode with the extra headroom
(a new switch like the existing `-IsCpuEncode`/`-RemuxTwoStage` precedents) —
preservation encodes are CPU encodes PLUS one stream-copy of the video track.

### 6.3 x265 parameter injection (`New-EncodeVideoFlags`, encode_policy.ps1)

Status 2026-06-22: the encode argument builders now thread
`-DolbyVisionRpuPath`, `-DolbyVisionTargetProfile`, and `-Hdr10PlusJsonPath`
through `New-EncodeAttemptPlan`/`New-EncodeVideoFlags` and descriptor-owned
libx265 flag generation. The implementation is intentionally guarded to CPU
libx265 HDR plans and Dolby Vision target profile `8.1`. Dolby Vision encode
uses FFmpeg native `-dolbyvision true`; the previously planned
`dolby-vision-rpu=` x265 param is not passed because local FFmpeg/libx265 rejects
that CLI-only option through `-x265-params`. HDR10+ JSON still uses a relative,
colon-free `dhdr10-info=` artifact path. `Resolve-DynamicHdrX265ArtifactPaths`
converts successful extraction outputs into x265-safe relative paths, fails
closed for missing artifacts, rooted paths, cross-drive/colon-bearing paths, or
missing base directories, and the x265 parameter builder rejects rooted artifact
paths directly. Extraction-to-encode invocation, policy routing, force-CPU
activation, output verification, and Dolby Vision P8.1 real-media proof are in
place; representative HDR10+ proof remains open.

New parameters (default `''`/`$false`, threaded through `New-EncodeAttemptPlan`
exactly like `Hdr10MasterDisplay` at encode_policy.ps1:372-391):
`-DolbyVisionRpuPath`, `-DolbyVisionTargetProfile` (string, only `'8.1'`
supported), `-Hdr10PlusJsonPath`.

Inside the existing CPU/x265 `$IsHDR` block (after the `max-cll` append,
encode_policy.ps1:215-220):

```powershell
if (-not [string]::IsNullOrWhiteSpace($DolbyVisionRpuPath)) {
    $flags += @('-dolbyvision', 'true')
    $x265ParamPairs.Add("dolby-vision-profile=$DolbyVisionTargetProfile")
    # x265 hard-requires VBV with dolby-vision-profile; without these it
    # errors out. L5.1-high-tier-safe defaults, above every route bitrate cap.
    $x265ParamPairs.Add('vbv-maxrate=50000')
    $x265ParamPairs.Add('vbv-bufsize=50000')
}
if (-not [string]::IsNullOrWhiteSpace($Hdr10PlusJsonPath)) {
    $x265ParamPairs.Add("dhdr10-info=$Hdr10PlusJsonPath")
}
```

- VBV values are decision log D6; 50000/50000 is the proposed default. They cap
  bitrate spikes, interacting with CRF — call this out in the change packet and
  the real-media worksheet (verify no visible quality regression vs a non-DoVi
  CRF encode of the same source).
- TRAP T4 (paths): x265 splits params on `:`, so `C:\...` is unparseable. The
  MANDATED approach: compute
  `[System.IO.Path]::GetRelativePath((Get-Location).Path, $rpuPath)` at plan
  time; if the result still contains `:` (processing dir on a different drive
  than the process CWD — likely, scratch is often not C:), `Export-...` must
  COPY the artifacts to a GUID-named subdirectory of the process CWD's temp
  area... NO — simpler and approved design: pass paths through x265's accepted
  alternative. x265 does not support escaping colons. Therefore: if a
  colon-free relative path cannot be constructed, `Resolve-DynamicHdrEncodePlan`
  must return `Supported=$false, ReasonCode='dynamic_hdr_rpu_path_unrepresentable'`
  and the policy fallback (remux/review) applies. Extending the ffmpeg runner
  with a working-directory parameter (only `worker_process.ps1:71` uses one
  today) is the clean long-term fix — decision log D7; do not do it ad hoc.
- These params must be unreachable on any NVENC branch (trap T5): assert in the
  unit check that `Get-EncodeEncoderKind` != 'nvenc' whenever the new pairs are
  present in the produced argument list.

### 6.4 Forcing the CPU path in `Do-Encode`

When `$preservePlan.Action -eq 'encode_preserve'`:
- Set a local `$forceCpuForDynamicHdr = $true` and OR it into the existing
  `$skipGpuDueToProbe` handling (encode.ps1:150, 194-200, 240-247) so the GPU
  primary and safe-retry attempts are skipped without burning ffmpeg launches —
  the mechanism already exists, reuse it; the log line and the
  `encoder_fallback_started` event Data must say
  `trigger = 'dynamic_hdr_preservation'` (pattern at encode.ps1:154-161).
  CAUTION: do not let this path call `Invalidate-NvencAvailableProbe`; NVENC is
  healthy, just unsuitable — preservation must not poison the GPU cache for
  subsequent non-DoVi files (the existing `$skipGpuDueToProbe` guard at
  encode.ps1:259 already protects this; keep it true for the new flag too).
- The CPU plan call (encode.ps1:297) gains the three new arguments. The CPU
  space re-check (encode.ps1:291) and `Acquire-CpuEncodeMutex` (encode.ps1:329)
  apply unchanged.
- `$recordEncodeAttempt` rows (encode.ps1:79-105) gain
  `dynamic_hdr_preservation = [bool]`, flowing into the sidecar's
  `encode_attempts` (publish_completion.ps1:149-154) for free.
- Evidence `outcome` becomes `preserved_encode_rpu` /
  `preserved_encode_hdr10plus` / `preserved_encode_both` /
  `converted_p7_to_p81` (set converted flag additionally when P7), pending §7
  verification flip to `verified_*`.

### 6.5 Phase 3 tests and validation

- `ops/pipeline/tests/Unit/Invoke-EncodeFlagPolicyChecks.ps1` now covers the
  x265 parameter-wiring snapshot plus guards for NVENC, SDR, unsupported target
  profile, and colon-bearing Windows paths.
- NEW `ops/pipeline/tests/Unit/Invoke-DynamicHdrEncodePolicyChecks.ps1`:
  `Resolve-DynamicHdrEncodePlan` truth table (every §2.1 row x every policy
  value x tool-present/absent x container mkv/mp4 — enumerate, this is ~40 cheap
  asserts); `New-EncodeVideoFlags` emits/omits the param pairs correctly (CPU
  with RPU, CPU without, NVENC never); VBV pairs present iff RPU present;
  relative-path/colon rejection logic.
- Agent-side integration with SYNTHETIC fixtures (§9.1): full Do-Encode on a
  6-second DoVi 8.1 fixture and an HDR10+ fixture in a sandbox LocalBase
  (the end-to-end smoke harness pattern), asserting tool invocations, FFmpeg
  native DoVi flag/x265 args (via the repro/arg logging), and a non-empty
  output.
- End-to-end smoke, `-ValidateOnly`, dump parity (no new keys this phase, so
  byte-identical).
- Operator (REQUIRED): real P7 UHD-BD remux source and real HDR10+ source
  through `preserve_or_remux` and `preserve_or_review`; confirm review routing,
  remux forcing, and at least one successful preserved CPU encode; playback
  check deferred to Phase 4 worksheet but an early eyeball on a DoVi-capable
  Plex client is encouraged.

Acceptance: preserved encode produced for 8.1 and 7→8.1; profile 5 and mp4
container route to remux/review per policy; extraction failure never yields a
silently-flattened publish; `warn` policy still byte-identical behavior to
Phase 1.

---

## 7. Phase 4 — Output verification gate

### 7.1 `Test-DynamicHdrOutputIntegrity` (in `dynamic_hdr.ps1`)

Inputs: `-OutputPath`, `-Evidence` (the current file's evidence object),
`-ExpectedRpuFrameCount` (from §6.2 step 3; 0 = skip count check, remux path).
Checks, fail-closed like `Test-DurationMatch`:
1. ffprobe on output: DOVI configuration record present with expected profile
   (8 for preserved encodes; source profile for remux) when evidence expects DoVi.
2. `dovi_tool extract-rpu` round-trip on the output's extracted HEVC: succeeds,
   and frame count == expected (encode path) or == source RPU count (remux path,
   when cheaply obtainable — else presence-only).
3. `hdr10plus_tool extract` non-empty when evidence expects HDR10+.
Result object: `Ok`, `Reason`, `ErrorCode='DYNAMIC_HDR_VERIFY_FAILED'`, plus a
`verification` sub-map for the sidecar (Appendix B).

Cost note: round-tripping a full UHD movie's video stream is minutes of I/O.
Acceptable for preserve modes (correctness over speed); under `warn` policy the
verifier must NOT run (evidence stays `expected_*`). Document this in the
function header.

### 7.2 Hook points

- encode.ps1: after `Test-DurationMatch` (line 454), before size policy/publish.
  Failure → `Register-SourceFailure` (classification `transient`, the encode can
  be retried; `operator_required` if the second attempt also fails — follow the
  existing retry-escalation behavior in failure_state.ps1) and `return $false`.
  No publish of unverified output in preserve modes.
- remux.ps1: after `Test-DurationMatch` (line 402), same shape, only when
  evidence expects metadata and policy is a preserve mode.
- On success, flip evidence `outcome` to `verified_preserved_*` and attach the
  `verification` map; on parked pushes, carry evidence through the park manifest
  so drained sidecars get it (this closes the §4.6 gap; touch
  `pending_park_transaction.ps1` / `pending_drain_transaction.ps1` minimally —
  the park manifest already round-trips `sidecarExtra`-shaped data, follow
  `route_plan`'s carry pattern).

### 7.3 Validation

Unit checks with stubbed tools (verifier truth table, fail-closed on tool
absence in preserve modes); full agent-side fixture run (encode + remux,
verify pass and a deliberately corrupted-output verify fail); end-to-end smoke.
Operator: the FULL release gate + real-media validation worksheet across the
fixture matrix (§9.2) INCLUDING playback on a DoVi-capable display/Plex client
(decision log D9: which client/display). This is the §7 sign-off for the whole
epic; until it passes, `DynamicHdrPolicy` default stays `warn`.

---

## 8. Documentation and cross-cutting (each phase)

- CHANGELOG.md entry per phase (operator-visible behavior only).
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`: read before Phases 2-4; if the
  register enumerates FFmpeg/publish invariants, propose additions for the new
  tools and the verification gate (operator approves the wording).
- docs/SESSION.md: scope block before work, handoff after, per the established
  format (in-scope files, validation rung, NOT-self-certified list).
- Summaries regenerated for every touched file; module count note in the
  change packet when `dynamic_hdr.ps1` lands.

---

## 9. Fixtures and real-media matrix

### 9.1 Synthetic fixtures (agent-runnable, tiny, no real media needed)

Build once in Phase 2, store under the operator-approved fixture root (decision
log D4; precedent: `E:\Videos\TdarrMatrix\TestFixtures\` — NOT under any source
library root, per AGENTS.md §9):

1. Base: `ffmpeg -f lavfi -i testsrc2=duration=6:size=1920x1080:rate=24 -c:v libx265
   -pix_fmt yuv420p10le -x265-params "hdr10=1:repeat-headers=1:colorprim=bt2020:
   transfer=smpte2084:colormatrix=bt2020nc:master-display=G(13250,34500)B(7500,3000)
   R(34000,16000)WP(15635,16450)L(10000000,1)" base_hdr10.mkv` (6 s, ~1 MB).
2. DoVi 8.1 fixture: `dovi_tool generate` from a minimal generator JSON →
   RPU; `dovi_tool inject-rpu -i base.hevc --rpu-in rpu.bin -o dovi81.hevc`;
   mkvmerge into `fixture_dovi_p81.mkv`.
3. HDR10+ fixture: a minimal ST 2094-40 JSON (one scene; upstream repo carries
   examples) + `hdr10plus_tool inject` → `fixture_hdr10plus.mkv`.
4. P7 fixture: cannot be synthesized faithfully (EL); use a SHORT clip the
   operator cuts from a real P7 source (`mkvmerge --split parts:` on a UHD-BD
   remux) — operator-provided, documented in the worksheet.
5. Negative fixtures: plain `base_hdr10.mkv` (no dynamic metadata) and an SDR clip.

### 9.2 Real-media validation matrix (operator worksheet rows)

| # | Source | Policy | Expected |
| --- | --- | --- | --- |
| 1 | DoVi P7 UHD-BD remux | warn | encode proceeds, drop warning + evidence |
| 2 | DoVi P7 | preserve_or_remux, encode route | converted 7→8.1 CPU encode, verified, plays as DV |
| 3 | DoVi P7 oversized → remux fallback | preserve_or_remux | remux output verified, plays as DV |
| 4 | DoVi P5 (web-DL) | preserve_or_remux | forced remux, verified |
| 5 | DoVi P5 | preserve_or_review | review queue, no output |
| 6 | DoVi P8.1 (web-DL) | preserve_or_remux | preserved CPU encode, verified; Dolby Browser Test Kit P8.1 proof passed 2026-06-22 |
| 7 | HDR10+ (web-DL) | preserve_or_remux | dhdr10-info encode, verified, HDR10+ engages |
| 8 | HDR10 only | preserve_or_remux | normal GPU-first encode, outcome none_detected |
| 9 | SDR | any | zero probes, unchanged |
| 10 | DoVi source with dovi_tool removed | preserve_or_review | review with DYNAMIC_HDR_TOOL_MISSING |

Playback verification (rows 2,3,6,7) needs a DoVi/HDR10+-capable display and
Plex client; "plays as DV" means the display's DV indicator engages and no
purple/green tint (the classic broken-RPU symptom).

---

## 10. Decision log (operator must answer; do not guess)

- D1 (Phase 2): pin exact dovi_tool / hdr10plus_tool release versions.
- D2 (Phase 2): confirm `warn` as shipped default for `DynamicHdrPolicy`.
- D3 (Phase 2): binaries gitignored like ffmpeg, or LFS/tracked?
- D4 (Phase 2): fixture storage root.
- D5 (Phase 2, conditional): remediation choice if ffmpeg temp_av drops the DoVi
  config record (mkvmerge-direct for DoVi remuxes vs ffmpeg upgrade).
- D6 (Phase 3): VBV defaults (proposed 50000/50000) — confirm or tune.
- D7 (Phase 3, conditional): if scratch is on a different drive than the process
  CWD (likely), approve adding a working-directory parameter to the ffmpeg
  runner, or accept that preservation degrades to remux/review on this machine.
  This is THE most likely real-world blocker for Phase 3 — surface it early in
  Phase 2 by checking the live config's LocalBase drive vs the repo drive.
- D8 (post-Phase 3): whether/how to reprocess existing DoVi titles (NOT via a
  pipeline version bump — see trap T9; candidate: CSV rerun of selected titles).
- D9 (Phase 4): which display/client constitutes the playback rung.
- D10 (any phase): Plex compatibility report (`Write-PlexCompatibilityReport`,
  media_probe.ps1:805) could mention DV/HDR10+ — cosmetic, separate approval.

## 11. Known risks

- Profile 7 EL: discarded by design on encode (7→8.1). Purists lose the
  full-enhancement-layer signal; remux route keeps it. Stated in evidence
  (`converted_p7_to_p81`).
- dovi_tool CLI drift between versions (extract-rpu flags, info output format) —
  pinning (D1) + version captured in evidence mitigates.
- x265 build capability is environment-dependent — the capability probe, not an
  assumption, decides (§5.3); unsupported builds degrade to remux/review.
- RPU/frame misalignment if any future filter changes frame count — the Phase 4
  count check is the backstop; never add fps/trim filters to preserved encodes.
- Long CPU encodes for UHD DoVi (hours) — existing CPU mutex, timeout
  (`FFmpegCpuEncodeTimeoutSeconds`) and priority settings apply; warn the
  operator in docs that preserve modes trade throughput for fidelity.

## 12. Explicitly out of scope (entire epic)

Audio policy; subtitle paths; pending-publish drain semantics (beyond the
evidence carry in §7.2); queue/launch behavior; settings UI (named follow-up);
WebView completed-drawer badge (named follow-up); AV1/DoVi; MP4 DoVi muxing;
profile 5 re-encoding; any change to `Get-HDRState`, `source_media_profile.v1`,
or `Get-SourceHdr10MasteringMetadata`.

---

## Appendix A — Tool command reference (verify against pinned versions)

```text
# Detection (bundled ffprobe)
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name:stream_side_data_list -of json -- <file>
ffprobe -v error -select_streams v:0 -read_intervals "%+#24" -show_frames -show_entries frame=side_data_list -of json -- <file>

# Elementary stream
mkvextract tracks <in.mkv> <vid_tid>:<work.hevc>
ffmpeg -i <in> -map 0:v:0 -c:v copy -bsf:v hevc_mp4toannexb -f hevc <work.hevc>   # non-MKV

# Dolby Vision
dovi_tool extract-rpu -i <work.hevc> -o <rpu.bin>            # P8.1 as-is
dovi_tool -m 2 extract-rpu -i <work.hevc> -o <rpu.bin>       # P7 -> 8.1
dovi_tool info -i <rpu.bin> --summary                        # frame count
dovi_tool inject-rpu -i <enc.hevc> --rpu-in <rpu.bin> -o <out.hevc>   # contingency path only

# HDR10+
hdr10plus_tool extract -i <work.hevc> -o <meta.json>
hdr10plus_tool inject  -i <enc.hevc> -j <meta.json> -o <out.hevc>     # contingency path only

# x265 via ffmpeg (CPU branch only; relative, colon-free paths only)
-dolbyvision true -x265-params ...:dolby-vision-profile=8.1:vbv-maxrate=50000:vbv-bufsize=50000
-x265-params ...:dhdr10-info=<rel\meta.json>
```

## Appendix B — `dynamic_hdr` sidecar evidence schema (v1)

```text
dynamic_hdr = ordered map {
  schema_version        'dynamic_hdr_evidence.v1'
  probed                bool
  probe_error           string ('' when probed)
  dovi_present          bool
  dovi_profile          int (0 none)
  dovi_level            int (0 none)
  dovi_bl_compat_id     int (-1 none)
  dovi_el_present       bool
  hdr10plus_present     bool
  dynamic_metadata_present bool (dovi_present -or hdr10plus_present)
  policy                string (config value at run time; 'warn' implied in Phase 1)
  route                 'encode' | 'remux'
  outcome               'none_detected' | 'probe_failed' | 'will_drop_encode' |
                        'expected_preserved_remux' | 'preserved_encode_rpu' |
                        'preserved_encode_hdr10plus' | 'preserved_encode_both' |
                        'converted_p7_to_p81' | 'verified_preserved_remux' |
                        'verified_preserved_encode' | 'forced_remux' | 'blocked_review' |
                        'dropped'
  summary               string (one human-readable line)
  warning               string ('' unless metadata lost)
  tool_versions         { dovi_tool string; hdr10plus_tool string }   # Phase 2+
  verification          { checked bool; output_dovi_present bool;     # Phase 4
                          output_hdr10plus_present bool;
                          rpu_frame_count int; expected_frame_count int }
}
```

Three nesting levels max — safe inside the sidecar's `-Depth 10` (trap T6).
Fields are append-only; never repurpose an outcome value.
