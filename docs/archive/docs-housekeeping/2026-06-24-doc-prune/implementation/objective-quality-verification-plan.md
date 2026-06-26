# Implementation plan: objective quality verification (VMAF/SSIM/PSNR) after lossy encodes

Date: 2026-06-11
Audience: implementing AI agent (Codex)
Status: plan approved for handoff; NOT implemented
Risk class: AGENTS.md section 7 (FFmpeg invocation adjacency, publish gating, settings schema) -- the final
validation rung is operator-run real-media validation and is NOT agent-self-certifiable.
Effort: M (9 config keys across ~12 parity surfaces, 1 new engine module, 1 wiring point, completed-surface
carry, settings UI group, 1 new PS unit check).

Every file path, line anchor, function name, and test gate below was verified against the working tree on
2026-06-11 (branch `refactor/mediapipeline-entrypoint-slice`). If a line number has drifted, locate the quoted
anchor text instead -- do not guess.

---

## 0. Ground rules (read first, non-negotiable)

1. AGENTS.md is authoritative; read its sections 1-3, 5, 7, 8 before editing. This plan touches section 7
   areas (encode acceptance, publish gating, settings schema). Do not self-declare completion; end with the
   operator validation list in section 12.
2. Add a scope block to `docs/SESSION.md` (template in section 13) before editing. One domain set per the
   migration rules: this task spans `ops/pipeline/` + `src/mediapipeline/` + `apps/desktop/webview/static/` +
   `tests/`; the SESSION.md block names every file so the cross-domain scope is explicit and operator-approved.
3. Create a change packet under `ops/release/changes/unreleased/` (`MP-CHANGE-2026-06DD-NNN.json`; check
   existing packets for a free id) before or during edits; keep `files_touched` current; run
   `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage`
   before the final response.
4. Never commit, push, or stage unless the operator explicitly asks. Suggested branch (operator decision):
   `feat/quality-verification` off the current tip.
5. Bundled interpreters only: PowerShell tests via `pwsh`, Python via `apps\desktop\runtime\Python\python.exe`
   (it currently lacks pytest -- run with `-m unittest`). Bundled ffmpeg/ffprobe live at
   `ops\pipeline\tools\ffmpeg\bin\ffmpeg.exe` / `ffprobe.exe`.
6. The working tree may contain unrelated dirty files (e.g. regenerated summaries). Touch ONLY the files this
   plan names. After source edits, refresh summaries with
   `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths <each changed source file>`.
7. No emojis anywhere. ISO dates in saved notes. Match surrounding code style exactly (the engine uses
   explicit `[string]`/`[bool]` casts, `[ordered]@{}` evidence maps, `Write-Log "<CONTEXT>: msg" "LEVEL"`).
8. Update `CHANGELOG.md` with a short entry (AGENTS.md section 2: doc updates go in CHANGELOG, not new
   top-level status files). Do NOT create any new top-level `*.md`.

---

## 1. What is being built

After a lossy encode succeeds (existing duration verify passed), measure perceptual similarity of the encoded
temp output against the scratch source with the bundled ffmpeg's `libvmaf` (or `ssim`/`psnr`) filter. Record a
structured result on the completed sidecar/manifest so it surfaces on the Completed page trust fields. Map the
score to `pass | warn | fail`; on `warn`, log and flag; on `fail` with `QualityFailAction = block_review`,
reject the encode BEFORE publish through the existing failure-marker machinery (modeled exactly on the
existing strict size-guard rejection). Remux (stream-copy) paths never run it. Feature is OFF by default.

### Verified facts you can rely on (do not re-litigate)

- `ops\pipeline\tools\ffmpeg\bin\ffmpeg.exe` is ffmpeg 8.1 full build with `--enable-libvmaf`; the `libvmaf`,
  `ssim`, and `psnr` filters are present. Verified 2026-06-11.
- The libvmaf built-in default model works WITHOUT any external model file. Verified by running:
  `ffmpeg -hide_banner -f lavfi -i "testsrc2=duration=1:size=320x180:rate=10" -f lavfi -i "testsrc2=duration=1:size=320x180:rate=10" -lavfi "libvmaf=n_threads=2" -f null -`
  which printed `VMAF score: 99.742836`. Do NOT ship or reference a model file; do NOT pass `model=`.
- `ops\pipeline\tools\ffmpeg\bin\ffprobe.exe` exists.
- The encode flow, hook point, and all parity surfaces are as described in sections 4-9.

### Decisions already made (do not change without operator approval)

| Decision | Value | Rationale |
| --- | --- | --- |
| Default state | `EnableQualityVerification = $false` | additive, zero-risk rollout |
| Default metric | `vmaf` | perceptual; built-in model verified working |
| Default action | `warn_only` | VMAF cost + false-positive risk; operator opts into blocking |
| Fail action enum | `warn_only` \| `block_review` (NOT `park_pending`) | Parking into PendingServerPush is wrong here: the pending-drain flow exists to PUBLISH parked outputs later with manifest evidence (AGENTS.md section 3 rule 3). Parking a known-bad encode would auto-publish it on the next drain. `block_review` instead mirrors the existing strict size-guard path (`encode.ps1` ~line 506: `Register-SourceFailure -Classification 'operator_required'` + reject before publish + temp output cleaned by the existing finally block). The "never auto-publishes" goal is met with no pending-publish/drain changes. |
| New outcome codes | `ENCODE_QUALITY_BELOW_FLOOR`, `ENCODE_QUALITY_REVIEW` | the `ENCODE_` prefix makes every regex-derived metadata function (family/stage/handled-by) classify them correctly with minimal edits (section 6) |
| Failure stage string | `encode-quality-verify` | matches `Get-FailureCategory`'s existing `verify|validation` regex (failure_state.ps1:75) so it auto-classifies as `validation` with zero changes there |
| Progress stage | reuse existing `encode_verify` stage label with a quality-specific Status text | introducing a new stage string risks the stage-percent mapping in status code (section 7 adjacency); reuse is what the CPU-fallback label fix already does at encode.ps1:452 |
| Thresholds | interpreted in the selected metric's units; defaults assume vmaf (warn < 90, fail < 75) | single pair of keys; help text + an optional risk rule cover the ssim/psnr unit mismatch |
| Tool errors fail OPEN | a verification infrastructure error (ffmpeg crash, timeout, parse failure, stop request) records outcome `error`/`stopped`, logs WARN, and NEVER blocks publish | quality verification is an advisory gate; only a successfully measured below-floor score may block |
| Deferred publish (`DeferredPublish = $true`) | quality is still measured and can still block (the block happens before any park), but the score record reaches the completed manifest only on the immediate-publish sidecar path in v1 | carrying the record through pending-park manifests and drain is section 7 pending-publish surface; explicitly out of scope (section 11) |

---

## 2. New config keys (9)

All are top-level pipeline config keys. NONE are library-overridable and NONE go into worker config
overrides (do not touch `Get-MediaPipelineLibraryOverrideConfigKeys`, `LIBRARY_OVERRIDE_KEYS_BY_GROUP`, or the
nested allowlists inside the JSON schema -- see section 3 trap T2).

| Key | Type | Default | Constraints / choices |
| --- | --- | --- | --- |
| `EnableQualityVerification` | bool | `$false` | |
| `QualityMetric` | choice | `'vmaf'` | `vmaf`, `ssim`, `psnr` |
| `QualitySampleMode` | choice | `'sampled'` | `sampled`, `full` |
| `QualitySampleSeconds` | int | `10` | clamp 2..60 |
| `QualitySampleCount` | int | `3` | clamp 1..10 |
| `QualityWarnThreshold` | double | `90` | metric units; `<= 0` disables the warn tier |
| `QualityFailThreshold` | double | `75` | metric units; `<= 0` disables the fail tier |
| `QualityFailAction` | choice | `'warn_only'` | `warn_only`, `block_review` |
| `QualityVerifyTimeoutSeconds` | int | `1800` | clamp 60..21600; per ffmpeg invocation |

Insertion anchor in EVERY ordered surface: immediately after `OutputValidationDurationToleranceSeconds` and
before `AllowSystemTools` (the existing output-validation cluster). Keep the 9 keys in the table's order
everywhere -- two independent checks assert exact sequence equality across surfaces.

---

## 3. Phase 1 -- config key registration (all parity surfaces)

The parity gates are `ops\pipeline\tests\Unit\Invoke-ConfigKeyRegistryChecks.ps1` (asserts PS registry order ==
PS schema order == JSON schema property order) and `tests\python\desktop\test_config_keys.py` (asserts Python
order/sets == PS registry == JSON schema == webview consumers). Work surface-by-surface, then run both gates
and iterate on their drift messages until green.

1. `ops/pipeline/engine/config/config_keys.ps1` -- add 9 entries to `$script:MediaPipelineConfigKeyRegistry`
   after `OutputValidationDurationToleranceSeconds = 'OutputValidationDurationToleranceSeconds'` (line ~126).
   Form: `EnableQualityVerification = 'EnableQualityVerification'` etc. Do NOT add to
   `$script:MediaPipelineNetworkConfigKeys`.
2. `ops/pipeline/engine/config/choice_registry.ps1` -- add three function triples mirroring the
   `Get-MediaPipelineSizeGuardModeNames` / `...Default` / `Resolve-MediaPipelineSizeGuardMode` pattern
   (lines 113-237):
   - `Get-MediaPipelineQualityMetricNames` (`vmaf`,`ssim`,`psnr`), `...Default` (`vmaf`),
     `Resolve-MediaPipelineQualityMetric`
   - `Get-MediaPipelineQualitySampleModeNames` (`sampled`,`full`), `...Default` (`sampled`),
     `Resolve-MediaPipelineQualitySampleMode`
   - `Get-MediaPipelineQualityFailActionNames` (`warn_only`,`block_review`), `...Default` (`warn_only`),
     `Resolve-MediaPipelineQualityFailAction`
   Each resolver: trim/lowercase, return default on empty/unknown (copy the SizeGuardMode resolver verbatim).
3. `ops/pipeline/engine/config/default_values.ps1` -- add the 9 defaults at the same relative position as the
   registry (near `SizeGuardMode = Get-MediaPipelineSizeGuardModeDefault`, line ~233 region; place them after
   the OutputValidation* defaults). Use the choice-registry default functions for the three choice keys.
4. `ops/pipeline/engine/config/config_schema.ps1` -- this file feeds `Get-MediaPipelineConfigOrderedKeys`,
   whose sequence must equal the registry order. Open it, find the `OutputValidationDurationToleranceSeconds`
   entry, and add the 9 keys there in table order, copying the entry shape of typed neighbors (bool like
   `EnableIntegrityCheck`, int like `OutputValidationProbeTimeoutSeconds`, choice like `SizeGuardMode`,
   numeric/double like `OutputSizeMultiplier`).
5. `ops/pipeline/config/schemas/media_pipeline_config.schema.json` -- add the 9 keys to the TOP-LEVEL
   `properties` object only, at the same anchor position. Mirror the property-body style of the
   OutputValidation* neighbors (some properties are typed, some are `{}` -- copy what the neighbors do).
   TRAP T2: this file also contains nested allowlists with `"additionalProperties": false` (library-profile
   overrides ~line 230, `WorkerConfigOverrides` ~line 334). Do NOT add the quality keys there.
6. `ops/pipeline/engine/config/runtime_config.ps1` -- in `Initialize-MediaPipelineRuntimeConfig`, add a
   resolution block per key producing `$script:`-scoped runtime values, modeled on the `SizeGuardMode` block
   (lines 281-285):
   ```powershell
   $script:EnableQualityVerification = if ($config.ContainsKey('EnableQualityVerification')) { [bool]$config['EnableQualityVerification'] } else { $false }
   $script:QualityMetric = if ($config.ContainsKey('QualityMetric')) { Resolve-MediaPipelineQualityMetric -Metric ([string]$config['QualityMetric']) } else { Get-MediaPipelineQualityMetricDefault }
   # ... QualitySampleMode / QualityFailAction via their resolvers;
   # ints/doubles with the file's existing numeric-coercion + clamp idiom (find how
   # TransientFailureRetryLimit or the timeout keys are coerced and copy it; clamp to section 2 ranges)
   ```
   Also add `$script:LastQualityVerification = $null` next to the existing
   `$script:CurrentSizePolicyResult = $null` initialization (line ~332).
   Then add the 9 resolved fields to `Get-MediaPipelineResolvedConfigDump` (the parity oracle; currently 99
   fields) so the dump stays complete. NOTE: any locally cached dump baselines (e.g.
   `%TEMP%\mp_refactor_baseline\dump_before.json` from the entrypoint-slice work) become stale by design;
   regenerate before/after comparisons inside THIS task only against a fresh pre-change dump.
7. Config templates -- add the 9 keys with literal defaults (`'vmaf'`, `$false`, etc.) at the same anchor in:
   - `ops/pipeline/config/MediaPipeline_config_template.psd1`
   - `ops/pipeline/config/profiles/Default.psd1`
   - any other `ops/pipeline/config/profiles/*.psd1` that lists the OutputValidation* cluster (enumerate the
     directory; keep profiles consistent with how they handle other optional keys -- if a profile omits the
     cluster entirely, leave it alone).
   Do NOT edit the operator's live gitignored `MediaPipeline_config.psd1` or the per-user copy under
   `%LOCALAPPDATA%`; absent keys resolve to defaults by design.
8. Python key order/groups -- `src/mediapipeline/core/kernel/config_key_order.py` defines
   `CONFIG_KEY_ORDER` / `ALL_CONFIG_KEYS` / `PYTHON_SCHEMA_CONFIG_KEYS`; `config_key_groups.py` defines the
   `KEY_*` constants. Add the 9 keys to the order tuple at the registry anchor, add 9 `KEY_*` constants
   following the file's naming convention (inspect neighbors; expected form `KEY_ENABLE_QUALITY_VERIFICATION =
   "EnableQualityVerification"` etc.), and add them to whichever group/partition set the test
   `test_desktop_managed_keys_match_python_schema_and_all_config_key_partition` requires -- the quality keys
   are desktop-managed (they get settings-UI field definitions in step 10), so they belong with the managed
   partition that `SizeGuardMode` is in. Let the test's error message drive the exact set membership.
9. `src/mediapipeline/contracts/config.py` -- add the 9 keys to `PS_CONFIG_KEY_ORDER` (line ~73) at the
   anchor (after `OutputValidationDurationToleranceSeconds`, before `AllowSystemTools`). This file also
   contains other key tuples/groupings (a Python-schema tuple ending near line 71, an `"editor"` grouping near
   line 431); run `test_config_keys.py` + `test_metadata_contract.py` and follow their drift errors for which
   of those also need the keys. Do not guess -- the tests name missing keys explicitly.
10. Settings field definitions -- `src/mediapipeline/core/config/metadata_parts/video_fields.py` (or
    `basic_processing.py` if video_fields turns out to be encoder-slider-only -- pick the part file whose
    `page`/`section` values fit): add 9 definition dicts mirroring the `SizeGuardMode` entry shape
    (basic_processing.py lines 185-195): `page`, `section: "Quality Verification"`, `key`, `label`, `kind`
    (`bool` / `combo` / `int` / `float` equivalents -- copy `kind` strings from existing bool/int/float
    neighbors, do not invent), `choices`/`choice_help` for the three combos, `default` matching section 2
    EXACTLY, and `help` text. Help for the thresholds MUST state: "Interpreted in the selected metric's
    units. Defaults assume VMAF (0-100). For SSIM use 0-1 (e.g. warn 0.95 / fail 0.90); for PSNR use dB
    (e.g. warn 38 / fail 32). 0 disables the tier." Help for `QualityFailAction` MUST state that
    `block_review` rejects the encode before publish and routes the source to operator review.
11. OPTIONAL but recommended -- `src/mediapipeline/desktop/application/settings_risk_policy_rules.py`: add
    rules mirroring the SizeGuardMode rules (lines ~257-276): (a) `QualityFailAction == "block_review"` ->
    medium, "encodes measuring below the quality floor will fail before publishing; validate thresholds with
    real media first"; (b) `QualityMetric == "ssim"` (or `psnr`) while either threshold is still > 1 (ssim)
    -> high, "threshold appears to be in VMAF units for a non-VMAF metric; every encode will fail/warn".
    Use the `KEY_*` constants (test `test_settings_policy_config_lookups_use_named_constants` enforces this).
    Update `tests/python/desktop/test_settings_risk_policy_rules.py` accordingly.

Phase 1 gates (all must pass before Phase 2):
```powershell
pwsh -File ops\pipeline\tests\Unit\Invoke-ConfigKeyRegistryChecks.ps1
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_config_keys tests.python.desktop.test_metadata_contract -v
pwsh -File ops\pipeline\entrypoints\MediaPipeline.ps1 -ConfigPath ops\pipeline\config\MediaPipeline_config_template.psd1 -ValidateOnly
```
(The exact unittest module path syntax: run from repo root with the env the existing tests document; if
`-m unittest` discovery needs `PYTHONPATH`, mirror what docs/SESSION.md handoffs used: `PYTHONPATH=<root>\src`.)

---

## 4. Phase 2 -- new engine module `ops/pipeline/engine/verify/quality.ps1`

New domain directory `ops/pipeline/engine/verify/` (allowed: `ops/pipeline/engine/<domain>/<role>.ps1` is the
sanctioned pattern). Header comment mirrors sibling modules (see `failure_codes.ps1` lines 1-15 style).

The module defines six functions. Four are PURE (no I/O, no `$script:`) so the unit check can test them
without ffmpeg; two orchestrate.

### 4.1 `Get-MediaQualityStreamInfo -FilePath <string> -TimeoutSeconds <int>`
ffprobe wrapper. Invocation (uses the ambient `Invoke-FFprobeCommand` from `shared/native.ps1`, which already
handles timeout, stop-awareness, events, and `$ffprobePath` resolution):
```powershell
$args = @('-v','error','-select_streams','v:0',
          '-show_entries','stream=width,height,avg_frame_rate,pix_fmt,duration:format=duration',
          '-of','json','-i',$FilePath)
$result = Invoke-FFprobeCommand -ArgumentList $args -TimeoutSeconds $TimeoutSeconds -Stage 'quality-probe'
```
Parse stdout JSON. Return `[pscustomobject]` with: `Ok` (bool), `Width`, `Height` (int), `FrameRate` (string,
the raw `avg_frame_rate` ratio e.g. `24000/1001` -- keep as ratio text, pass straight into the filter),
`PixFmt` (string), `DurationSeconds` (double; prefer stream duration, fall back to format duration), `Error`
(string). Any probe failure -> `Ok = $false` (callers fail open).

### 4.2 `Get-MediaQualitySampleWindows -DurationSeconds <double> -SampleSeconds <int> -SampleCount <int>` (PURE)
Returns `@()` of start-offset doubles, or `$null` meaning "use full-file mode".
Rules (implement exactly; unit-tested):
- If `DurationSeconds <= 0` -> `$null` (cannot place windows; full mode).
- If `DurationSeconds <= (2.0 * $SampleSeconds * $SampleCount)` -> `$null` (sampling pointless; full mode).
- Otherwise: usable span starts at `0.05 * DurationSeconds` and ends at
  `(0.95 * DurationSeconds) - SampleSeconds` (skip intro/credits). Place `SampleCount` window starts evenly:
  for `i` in `0..(SampleCount-1)`, `start_i = spanStart + i * (spanEnd - spanStart) / max(1, SampleCount - 1)`;
  for `SampleCount = 1` use the span midpoint. Round to 3 decimals.

### 4.3 `New-MediaQualityFilterGraph -Metric <string> -RefInfo <object> -LogPath <string>` (PURE)
Builds the `-lavfi` graph string. Conventions that MUST hold (wrong order silently produces garbage scores):
- Input 0 = DISTORTED (the encoded temp output); input 1 = REFERENCE (the scratch source). libvmaf/ssim/psnr
  all take distorted/main first, reference second.
- Pixel format: `yuv420p10le` if `$RefInfo.PixFmt -match '10|12'` else `yuv420p`.
- Both branches get `setpts=PTS-STARTPTS` then `fps=fps=<RefInfo.FrameRate>` (guards VFR/fps drift); the
  distorted branch additionally gets `scale=<RefW>:<RefH>:flags=bicubic` (no-op when dimensions match).
- Metric tails:
  - vmaf: `libvmaf=log_fmt=json:log_path=<escapedLogPath>:n_threads=<min(8, [Environment]::ProcessorCount)>`
  - ssim: `ssim` (parse stderr; no log file)
  - psnr: `psnr` (parse stderr; no log file)
- Resulting shape (vmaf example):
  `[0:v]setpts=PTS-STARTPTS,fps=fps=24000/1001,scale=1920:1080:flags=bicubic,format=yuv420p[dist];[1:v]setpts=PTS-STARTPTS,fps=fps=24000/1001,format=yuv420p[ref];[dist][ref]libvmaf=log_fmt=json:log_path=...`
- TRAP T3, log-path escaping inside a filter graph on Windows: replace every `\` with `/`, then escape the
  drive colon as `\:` (so `C:\Users\x\log.json` -> `C\:/Users/x/log.json`). Implement as a small private
  helper inside this function and unit-test it.

### 4.4 `ConvertFrom-MediaQualityToolOutput -Metric <string> -LogJsonPath <string> -StdErrText <string>` (PURE)
Returns `[pscustomobject] @{ Ok; Score; Error }`.
- vmaf: read the JSON file; score = `pooled_metrics.vmaf.mean`. The libvmaf JSON shape is
  `{"frames":[...], "pooled_metrics": {"vmaf": {"min":..,"max":..,"mean":..,"harmonic_mean":..}}}`. Missing
  file/key/unparseable -> `Ok = $false`.
- ssim: regex the LAST `All:([0-9.]+)` occurrence in stderr (filter summary line looks like
  `[Parsed_ssim_0 @ ...] SSIM Y:0.98... All:0.978...`).
- psnr: regex the LAST `average:([0-9.inf]+)` in stderr (`PSNR y:.. average:43.21 ..`); map `inf` to 100.0
  (identical streams).

### 4.5 `Invoke-MediaQualityVerification -ReferencePath -DistortedPath -Metric -SampleMode -SampleSeconds -SampleCount -TimeoutSeconds`
Orchestrator. Steps:
1. Probe both files with 4.1 (timeout: use the existing `OutputValidationProbeTimeoutSeconds` ambient
   `$script:` value if defined, else 30). Reference probe failure or `DurationSeconds <= 0` -> return an
   `error` record (fail open). Distorted probe failure -> same.
2. Windows: if `SampleMode -eq 'sampled'`, call 4.2; `$null` -> full mode.
3. Per window (or once for full mode), build the ffmpeg argument array. Sampled windows use accurate input
   seeking applied to BOTH inputs (ffmpeg `-ss` before `-i` is frame-accurate decode-and-discard, so both
   sides land on the same timestamps):
   ```powershell
   $args = @('-hide_banner','-nostats','-y',
             '-ss',$start,'-t',$SampleSeconds,'-i',$DistortedPath,
             '-ss',$start,'-t',$SampleSeconds,'-i',$ReferencePath,
             '-lavfi',$filterGraph,'-f','null','-')
   ```
   Full mode omits the `-ss`/`-t` pairs. Log files (vmaf) go to unique names under the pipeline temp dir --
   reuse however the engine resolves its temp/scratch working dir (look at how `encode.ps1` names `$tempOut`
   and place the json next to the pipeline log temp area, NOT next to media outputs); always delete them in a
   `finally`.
4. Run via `Invoke-FFmpegCommand -ArgumentList $args -TimeoutSeconds $TimeoutSeconds -Stage 'encode-quality-verify' -ProcessPriority 'BelowNormal'`
   (native.ps1:606; it resolves `$ffmpegPath`, enforces timeout, emits tool_started/tool_completed events, and
   honors stop requests). Nonzero exit / `TimedOut` / `Stopped` -> abort remaining windows, fail open with
   outcome `error` (or `stopped`).
5. Check `$script:StopRequested` between windows; if set, return outcome `stopped` (fail open).
6. Aggregate: `Score` = arithmetic mean of window scores (3 decimals); also keep `MinWindowScore` and the
   per-window list.
7. Return record `[ordered]@{}` (this exact map is what lands in the sidecar -- keep keys snake_case like
   sibling evidence maps):
   ```
   schema = 'quality_verification.v1'; diagnostic_only = $false
   enabled = $true; attempted = $true
   metric; score; min_window_score; window_scores = @(...); window_starts = @(...)
   sample_mode  ('sampled'|'full'); sample_seconds; sample_count
   reference_path; distorted_path  (full paths; sidecars already carry full paths)
   aligned_scale = <bool>; aligned_fps = <string ratio>; pixel_format = <string>
   duration_seconds = <measure wall time>; tool_error = <''|text>
   outcome = ''   # filled by 4.6
   ```

### 4.6 `Resolve-MediaQualityOutcome -Record <object> -WarnThreshold <double> -FailThreshold <double> -FailAction <string>` (PURE)
Returns `[pscustomobject]@{ Record; Warn; Block }` where Record is the input map with `outcome`,
`warn_threshold`, `fail_threshold`, `fail_action` filled in.
Mapping (exact, unit-tested):
- `tool_error` non-empty or `score` null -> outcome `error` (or `stopped` if the run was stopped);
  `Warn = $false; Block = $false`.
- `FailThreshold > 0` and `score < FailThreshold` -> outcome `fail`; `Warn = $false`;
  `Block = ($FailAction -eq 'block_review')`.
- else `WarnThreshold > 0` and `score < WarnThreshold` -> outcome `warn`; `Warn = $true; Block = $false`.
- else outcome `pass`; both false.

### 4.7 Module registration (TRAP T1 -- the loader fails FATAL on drift)
`ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1` enforces that `$engineModulePaths` (hashtable,
line 42) and `$engineModuleLoadOrder` (array, line 92) describe the SAME set (currently 46 modules). Add BOTH:
- Manifest entry: `'QualityVerify.ps1' = Join-Path $repoRootForModules 'ops\pipeline\engine\verify\quality.ps1'`
  (alphabetical-ish placement near the other entries; the hashtable order does not matter).
- Load order: insert `'QualityVerify.ps1'` immediately AFTER `'MediaProbe.ps1'` in `$engineModuleLoadOrder`
  (it depends on `Native.ps1` for the Invoke-* wrappers, loaded earlier; nothing depends on it).
Any fatal path you add inside a dot-sourced slice must set `$startupFatalExitCode` (see the comment at
module_loader.ps1:107) -- but quality.ps1 is an engine module (function definitions only, no top-level fatal
paths), so this should not arise.

Phase 2 gates:
```powershell
pwsh -NoProfile -Command "[System.Management.Automation.Language.Parser]::ParseFile('ops\pipeline\engine\verify\quality.ps1', [ref]$null, [ref]$errs) | Out-Null; $errs"
pwsh -File ops\pipeline\entrypoints\MediaPipeline.ps1 -ConfigPath ops\pipeline\config\MediaPipeline_config_template.psd1 -ValidateOnly   # loader contract check passes = module wired
```

---

## 5. Phase 3 -- failure/outcome codes

File: `ops/pipeline/engine/shared/failure_codes.ps1`.

1. Add `'ENCODE_QUALITY_BELOW_FLOOR'` and `'ENCODE_QUALITY_REVIEW'` to `Get-MediaPipelineKnownOutcomeCodes`
   (the alphabetized list starting line ~63; insert after `'ENCODE_OUTPUT_MISSING'` /
   `'ENCODE_SIZE_GUARD_EXCEEDED'` keeping alphabetical order).
   TRAP T4: do NOT add them to `Get-MediaPipelineKnownFailureCodes` -- that list is bidirectionally checked
   against `return 'CODE'` statements in classifier functions by
   `Invoke-FailureCodeRegistryChecks.ps1` (lines 28-36), and these codes are passed explicitly via
   `-ErrorCode`, never returned by a stderr classifier. `ENCODE_SIZE_GUARD_EXCEEDED` is the precedent: outcome
   list only.
2. `Get-MediaPipelineCodeRetryable` (line 260): a measured below-floor score is deterministic -- retrying
   re-encodes to the same result. Add `QUALITY_BELOW_FLOOR` to the non-retryable regex on line 270 (the one
   matching `TRUNCATED|CONTAINER_INVALID|...`): extend it with `|QUALITY_BELOW_FLOOR`.
   `ENCODE_QUALITY_REVIEW` stays retryable-true by falling through (it is a warn-tier marker, severity
   `warning` via the Retryable branch in `Get-MediaPipelineCodeOperatorSeverity`).
3. `Get-MediaPipelineCodeWhenFires` (line 295): extend the existing
   `'DURATION_MISMATCH|OUTPUT_MISSING|SIZE_GUARD'` arm (line 315) to
   `'DURATION_MISMATCH|OUTPUT_MISSING|SIZE_GUARD|QUALITY_BELOW_FLOOR|QUALITY_REVIEW'` (text already reads
   "Post-processing verification rejected the generated output." -- acceptable for both).
4. `Get-MediaPipelineCodeOperatorAction` (line 325): add an arm before `default`:
   ```powershell
   'QUALITY_BELOW_FLOOR|QUALITY_REVIEW' {
       return 'Compare the recorded quality score and metric against the configured thresholds; review the encode settings or thresholds before re-encoding or accepting the output.'
   }
   ```
5. `ops/pipeline/engine/failures/failure_state.ps1` -- two OPTIONAL fallback-map entries (the wiring always
   passes explicit `-ErrorCode`/`-SuggestedAction`, so these are belt-and-suspenders; add them for parity with
   `encode-verify`):
   - `Get-FailureSuggestedAction` stage map (line ~32 region): `'^encode-quality-verify$' { return 'Compare the recorded quality score against the thresholds; the encoded output was rejected before publish.' }`
   - `Get-MediaFailureCode` stage map (line ~243 region): `'^encode-quality-verify$' { return 'ENCODE_QUALITY_BELOW_FLOOR' }`
   `Get-FailureCategory` needs NO change -- stage `encode-quality-verify` matches the existing
   `verify|validation|integrity` regex (line 75) -> category `validation`.

Phase 3 gate: `pwsh -File ops\pipeline\tests\Unit\Invoke-FailureCodeRegistryChecks.ps1`

---

## 6. Phase 4 -- wiring the post-encode hook (`Do-Encode`)

File: `ops/pipeline/entrypoints/MediaPipeline/encode.ps1`. The hook goes between the existing duration verify
and the size-guard check. Anchor: the `if (-not (Test-DurationMatch ...))` block at lines 452-465 (stage
`encode_verify`); insert AFTER that block closes and BEFORE
`$sizePolicy = Test-MediaEncodeOutputSizePolicy ...` (line ~468).

Exact insertion (match the file's locals: `$localIn` = scratch source, `$tempOut` = encoded temp output,
`$file` = source FileInfo, `$verifyRoute` already computed at line 452, `$safeName` available):

```powershell
        # Objective quality verification (VMAF/SSIM/PSNR) -- advisory by default.
        # Runs only on the encode route; tool errors fail open (never block publish).
        $script:LastQualityVerification = $null
        if ($script:EnableQualityVerification) {
            Set-ProgressStage -Stage 'encode_verify' -Status "Verifying encode quality ($($script:QualityMetric))" -Route $verifyRoute -Percent $null -SaveNow
            $qualityRecord = Invoke-MediaQualityVerification -ReferencePath $localIn -DistortedPath $tempOut `
                -Metric $script:QualityMetric -SampleMode $script:QualitySampleMode `
                -SampleSeconds $script:QualitySampleSeconds -SampleCount $script:QualitySampleCount `
                -TimeoutSeconds $script:QualityVerifyTimeoutSeconds
            $qualityOutcome = Resolve-MediaQualityOutcome -Record $qualityRecord `
                -WarnThreshold $script:QualityWarnThreshold -FailThreshold $script:QualityFailThreshold `
                -FailAction $script:QualityFailAction
            $script:LastQualityVerification = $qualityOutcome.Record
            if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
                Write-PipelineEvent -EventType 'quality_verification' -Stage 'encode-quality-verify' `
                    -Route $verifyRoute -Status ([string]$qualityOutcome.Record['outcome']) `
                    -SourcePath $file.FullName -Data $qualityOutcome.Record | Out-Null
            }
            if ($qualityOutcome.Block) {
                $blockReason = "ENCODE quality below floor: $($script:QualityMetric) score $($qualityOutcome.Record['score']) < fail threshold $($script:QualityFailThreshold)"
                $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'operator_required' `
                    -Reason $blockReason -Stage 'encode-quality-verify' -ErrorCode 'ENCODE_QUALITY_BELOW_FLOOR' `
                    -SuggestedAction 'Compare the recorded quality score and metric against the configured thresholds; review encode settings or thresholds before re-encoding. The rejected encode was not published.'
                Write-Log "ENCODE QUALITY: $blockReason; rejecting encode before publish: $safeName" "ERROR"
                return $false
            }
            if ($qualityOutcome.Warn) {
                Write-Log "ENCODE QUALITY: $($script:QualityMetric) score $($qualityOutcome.Record['score']) below warn threshold $($script:QualityWarnThreshold) for $safeName (publishing; flagged for review)" "WARN"
            } elseif ([string]$qualityOutcome.Record['outcome'] -eq 'error') {
                Write-Log "ENCODE QUALITY: verification tool error ($($qualityOutcome.Record['tool_error'])); continuing without a score" "WARN"
            }
        }
```

Notes that matter:
- `return $false` rides the existing failure path: the `finally` block at lines ~547-552 already deletes
  `$tempOut` and cleans scratch exactly as the strict size-guard rejection does. Do not add bespoke cleanup.
- Do NOT touch `Do-Remux` (`ops/pipeline/entrypoints/MediaPipeline/remux.ps1`) -- remux skips by construction.
- Do NOT gate on route inside the hook; `Do-Encode` IS the encode route (the remux-vs-encode decision already
  happened in `Resolve-InitialMediaRoutePlan`, pipeline_processing.ps1:394).
- Parallel workers are fine: worker children run the same entrypoint + module loader, and the sidecar write
  happens in the same process scope where `$script:LastQualityVerification` was set.

### State lifecycle (TRAP T5 -- stale state leaks across queue items)
`ops/pipeline/engine/process/pipeline_processing.ps1` resets per-file script state in two places; add
`$script:LastQualityVerification = $null` to BOTH, next to the existing `$script:CurrentSizePolicyResult`
resets at line ~363 (pre-route reset) and line ~593 (the `finally` block).

---

## 7. Phase 5 -- carry the record into sidecar / completed manifest / evidence

1. Sidecar + completed manifest (the actual persistence): in
   `ops/pipeline/engine/publish/publish_completion.ps1`, after the `library_profile` / `folder_policy`
   conditional adds (lines 204-205), add:
   ```powershell
   if ($script:LastQualityVerification) { $sidecarExtra['quality_verification'] = $script:LastQualityVerification }
   ```
   `Write-Sidecar` then persists it to the `.pipeline.json` sidecar AND mirrors it into
   `LocalBase\State\Completed\completed_jobs.jsonl` (sidecar.ps1 `Add-CompletedJobsManifestEntry`) with zero
   further changes.
2. Verification-evidence summary (diagnostic surface on the process result): in
   `ops/pipeline/engine/paths/output_evidence.ps1`, extend `New-MediaPipelineVerificationEvidence`
   (line 238) with an OPTIONAL third parameter `$QualityEvidence = $null`. Inside, mirroring the size-guard
   pattern (lines 247-252):
   ```powershell
   if ($null -ne $QualityEvidence -and [bool]$QualityEvidence['attempted']) {
       [void]$checks.Add('quality_verification')
       $qualityOutcome = [string]$QualityEvidence['outcome']
       if ($qualityOutcome -eq 'warn') { [void]$warnings.Add('quality_warning') }
       if ($qualityOutcome -eq 'fail') { [void]$blockingFailures.Add('quality_below_floor') }
   }
   ```
   And add `quality_ref = if ($null -ne $QualityEvidence) { [string]$QualityEvidence['schema'] } else { '' }`
   to the returned map. Then at the single call site in `pipeline_processing.ps1` (line ~559-561) pass
   `-QualityEvidence $script:LastQualityVerification`. The parameter default keeps every other caller (tests)
   source-compatible.
3. Contract schema check: run `pwsh -File ops\pipeline\tests\Unit\Invoke-ContractSchemaChecks.ps1`. If it
   pins the verification-evidence or completed-job shapes, follow its failure message (additive fields on an
   `additionalProperties: true` schema normally pass; if a schema under
   `ops/pipeline/config/schemas/` or `src/mediapipeline/contracts/schemas/` enumerates sidecar/completed
   fields, add the `quality_verification` object there additively).

---

## 8. Phase 6 -- Python completed/trust surface

All target files are pure row/payload transformers; changes are additive.

1. `src/mediapipeline/core/completed/policy.py`:
   - New helper `completed_quality_fields(payload: dict[str, Any]) -> dict[str, Any]` modeled exactly on
     `completed_size_policy_fields` (line ~897): read `payload.get("quality_verification")`; when absent or
     not a dict return `{"quality_available": False, "quality_metric": "", "quality_score": None,
     "quality_outcome": "", "quality_min_window_score": None, "quality_sample_mode": "",
     "quality_warn_threshold": None, "quality_fail_threshold": None, "quality_blocked": False}`; when present,
     coerce defensively (floats via try/except, strings stripped) and set
     `quality_blocked = (outcome == "fail" and fail_action == "block_review")`.
   - In `completed_record_to_row` (the function containing line ~345
     `size_policy_fields = completed_size_policy_fields(...)`): compute
     `quality_fields = completed_quality_fields(record.payload)` and splat `**quality_fields` into the row
     dict next to `**size_policy_fields` (line ~386).
   - In the flag-derivation block (lines ~610-657 where `size_policy_*` flags are appended): append
     `"quality_below_floor"` when `quality_outcome == "fail"`, `"quality_review"` when `== "warn"`,
     `"quality_within_threshold"` when `== "pass"`. Outcomes `error`/`stopped`/absent add NO flag.
   - In the operator-guidance chain (lines ~709-720 pattern): add branches --
     `quality_below_floor` -> "Completed history reports an encode that measured below the configured quality
     floor. Inspect the recorded score, metric, and thresholds before trusting or re-running this output.";
     `quality_review` -> "Output published but its quality score fell below the warn threshold. Compare the
     score against the source before accepting it."
   - In the row-summary lines builder (the function near line ~784 that appends
     `completed_row_size_policy_line`): add an analogous `completed_row_quality_line(row)` ->
     `"Quality: vmaf 87.4 (warn < 90)"` style text when `quality_available`.
2. `src/mediapipeline/core/completed/trust_fields.py`:
   - In `_benign_trust_flags` (line 58): add `"quality_within_threshold"` to the `benign` set literal.
   - NO other change: `quality_review`/`quality_below_floor` flow through the existing
     `consistency_issues or trust_flags` review branch (line 111) by design.
3. `src/mediapipeline/core/completed/validation_state.py` -- ADDITIVE PASSTHROUGH ONLY (TRAP T6): in
   `validation_state_for_completed_row`, add to the returned dict:
   `"quality_score": row.get("quality_score")`, `"quality_metric": _row_text(row, "quality_metric")`,
   `"quality_outcome": _row_text(row, "quality_outcome")`. Do NOT add quality to `unavailable_reasons`, do NOT
   let it influence `status_state` or `playback_required`, and do NOT bump
   `VALIDATION_STATE_SCHEMA_VERSION`. Quality absence must not flip rows to `validation-needed` -- the feature
   is off by default and historical rows have no score.
4. Tests (extend the existing suites; find the test files exercising these modules with
   `Grep "completed_size_policy_fields|build_completed_row_trust_fields|validation_state_for_completed_row" tests\`):
   - `completed_quality_fields`: absent payload, full payload, malformed (non-dict, string score), blocked.
   - row flags + guidance for pass/warn/fail.
   - trust fields: `quality_within_threshold` is benign (state stays `consistent-looking`);
     `quality_below_floor` row reaches `review-before-rerun-or-cleanup`.
   - validation_state: fields pass through; a row WITHOUT quality keys yields identical
     `status_state`/`unavailable_reasons` to before (regression-pin TRAP T6).

Phase 6 gate (bundled Python, from repo root):
```powershell
.\apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_*completed*.py" -v
```
plus the specific suites you extended.

---

## 9. Phase 7 -- settings UI (builder group + metadata + inventories)

Model every step on the existing video builder; the wiring points are exact:

1. NEW `apps/desktop/webview/static/assets/settingsView.builders.quality.js` -- IIFE module exporting
   `createQualityDetailSettingsBuilder(deps)`, copied structurally from the smallest existing builder
   (inspect `settingsView.builders.file_safety.js` and `settingsView.builders.pending.js`; reuse the deps
   names used at settingsView.js:289-29x). It renders/binds the 9 keys: checkbox for the bool, selects for the
   3 combos (choices come from backend field definitions via the existing
   `settingsFieldDefinition`/`refreshSettingsSelectChoices` deps -- do NOT hardcode choice lists in JS),
   numeric inputs for the 4 numbers.
2. `apps/desktop/webview/static/index.html` -- add
   `<script src="/assets/settingsView.builders.quality.js"></script>` next to the existing builder script
   tags (line ~127).
3. `apps/desktop/webview/static/assets/settingsView.js` -- wire the new module exactly like
   `videoDetailSettingsBuilderModule` (line ~289): resolve the module from the window namespace the builders
   use, guard with `typeof ... === "function"`, pass the same deps object shape, and invoke it where the video
   builder is invoked.
4. `apps/desktop/webview/static/partials/page-settings.html` -- add the "Quality Verification" section markup
   with one DOM id per control. Follow the existing id convention from settingsMetadata.js
   (`settings-builder-<kebab>`): `settings-builder-quality-enable`, `settings-builder-quality-metric`,
   `settings-builder-quality-sample-mode`, `settings-builder-quality-sample-seconds`,
   `settings-builder-quality-sample-count`, `settings-builder-quality-warn-threshold`,
   `settings-builder-quality-fail-threshold`, `settings-builder-quality-fail-action`,
   `settings-builder-quality-timeout`. Place the section on the same page the field definitions use (step
   1.10), near the Routing/size-policy section.
5. `apps/desktop/webview/static/assets/settingsMetadata.js` --
   - add the 9 `["Key", "dom-id"]` pairs to `settingsBuilderFields` (line 3) using the ids above;
   - add a severity group entry (the array at line ~279): `{ name: "Quality verification", severity: "medium",
     keys: [ ...all 9... ] }`.
6. Inventory docs (test-enforced by `tests\webview\test_webview_inventory_docs.py` -- run it and let failures
   drive exact format): add the new DOM ids to `docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md`; add the new
   builder file/keys to `docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md` and
   `docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md`; add the 9 keys to
   `docs/architecture/CONFIG_KEY_GLOSSARY.md`. If the builder exports globals, mirror the convention in
   `docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`.
7. Gates:
   ```powershell
   node --check apps\desktop\webview\static\assets\settingsView.builders.quality.js
   node --check apps\desktop\webview\static\assets\settingsView.js
   .\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_config_keys -v   # webview-consumer key scan must still pass
   .\apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\webview -p "test_webview_inventory_docs.py" -v
   ```
   plus whichever `tests\webview\test_webview_*settings*` suites the repo runs for builder changes (discover
   with Grep; run the ones that execute settingsView.js).
   KNOWN PRE-EXISTING RED (do not "fix"): some webview static-assertion tests fail at HEAD against the
   operator's uncommitted rename/settings refactors (documented in docs/SESSION.md handoffs 2026-06-03/06-07).
   Record any such failure as pre-existing by reproducing it on the unmodified tree first.

---

## 10. Phase 8 -- new PS unit check `ops/pipeline/tests/Unit/Invoke-QualityVerificationChecks.ps1`

Model on `Invoke-MediaVerificationSafetyChecks.ps1` (same directory): `$ErrorActionPreference = 'Stop'`,
repo-root resolution via `Split-Path` chain, local `Assert-True`/`Assert-Equal`, a stub `Write-Log` capturing
to `$script:...Logs`, then dot-source ONLY `ops\pipeline\engine\verify\quality.ps1` (stub any ambient function
it touches, e.g. define no-op `Write-PipelineEvent` if needed).

Required cases:
1. `Get-MediaQualitySampleWindows`: duration 0 -> `$null`; duration 40/SampleSeconds 10/Count 3 -> `$null`
   (full-mode fallback, 40 <= 60); duration 3600/10/3 -> exactly 3 starts, first >= 180, last <= 3410,
   strictly increasing; Count 1 -> single midpoint window.
2. Filter-graph builder: vmaf graph contains `[0:v]` distorted-first ordering, `scale=1920:1080`,
   `fps=fps=24000/1001`, `format=yuv420p`; 10-bit ref pix_fmt -> `yuv420p10le`; Windows log path
   `C:\Temp\a.json` is escaped to `C\:/Temp/a.json`; ssim/psnr graphs end in `ssim`/`psnr` with no log_path.
3. Parser fixtures: write a temp JSON fixture
   `{"pooled_metrics":{"vmaf":{"min":80.1,"max":99.2,"mean":91.5,"harmonic_mean":91.0}}}` -> Score 91.5;
   missing file -> Ok false; ssim stderr fixture line with `All:0.978` -> 0.978; psnr fixture
   `average:43.21` -> 43.21; psnr `average:inf` -> 100.0.
4. `Resolve-MediaQualityOutcome` matrix: score 95 -> pass; 85 -> warn (Warn true, Block false); 70 +
   `warn_only` -> fail, Block FALSE; 70 + `block_review` -> fail, Block TRUE; tool_error set -> error, never
   Block even with `block_review`; thresholds 0 -> tiers disabled.
5. Live synthetic end-to-end (skip cleanly with a clear message if
   `ops\pipeline\tools\ffmpeg\bin\ffmpeg.exe` is missing): generate two 2-second 320x180 lavfi clips
   (identical testsrc2 -> expect vmaf > 90; then a heavily degraded second clip, e.g. re-encode with
   `-c:v libx264 -crf 51 -preset ultrafast` -> expect a measurably lower score), run
   `Invoke-MediaQualityVerification` in full mode against them, assert `outcome` ordering
   (identical > degraded) rather than absolute values. Stub the ambient `$ffmpegPath`/`$ffprobePath`
   variables and any `Get-NativeToolDefaultTimeoutSeconds` dependency, or dot-source
   `shared/native.ps1` + `shared/native_process_contracts.ps1` + `shared/executable_resolution.ps1` the way
   other Unit checks bring in their dependencies (follow `Invoke-MediaVerificationSafetyChecks.ps1`'s
   dot-source pattern at lines 29-30).
Print `OK: quality verification checks passed.` on success (house convention) and exit nonzero on failure.

---

## 11. Explicitly OUT OF SCOPE (do not do these)

- No changes to `Do-Remux`/remux.ps1, routing/decide modules, audio/subtitle policy, scratch copy, cleanup,
  queue, drain, or rename.
- No parking of quality-failed outputs into PendingServerPush, no pending-manifest or drain changes, no new
  `QualityFailAction` values. (Carrying the quality record through deferred-publish park/drain manifests is a
  documented follow-up requiring its own operator-approved plan.)
- No library-profile or worker-override exposure of the 9 keys.
- No new progress stage strings; no edits to status/eta mapping.
- No shipping/downloading VMAF model files; no ffmpeg bundle changes.
- No new top-level markdown; no edits to files in archived versioned workspaces, `LocalBase/`, `node_modules/`, `docs/archive/`.
- Do not "fix" the pre-existing red webview assertions or the self-skipping
  `Invoke-RuntimeConfigResolutionChecks.ps1` (stale pre-reorg paths) -- both are documented pre-existing.

---

## 12. Validation matrix and operator handoff

Agent-side, after all phases (every command from repo root):

| Gate | Command |
| --- | --- |
| PS parse | `Parser::ParseFile` on every edited/added .ps1 |
| Config registry parity | `pwsh -File ops\pipeline\tests\Unit\Invoke-ConfigKeyRegistryChecks.ps1` |
| Failure-code registry | `pwsh -File ops\pipeline\tests\Unit\Invoke-FailureCodeRegistryChecks.ps1` |
| Contract schemas | `pwsh -File ops\pipeline\tests\Unit\Invoke-ContractSchemaChecks.ps1` |
| New quality checks | `pwsh -File ops\pipeline\tests\Unit\Invoke-QualityVerificationChecks.ps1` |
| End-to-end smoke | `pwsh -File ops\pipeline\tests\Invoke-EndToEndSmokeChecks.ps1` (exit 0; ~40 s) |
| Entrypoint sanity | `-ValidateOnly` run (template config) shows clean startup, no reserved-key warnings, loader contract passes |
| Resolved-config dump | `-DumpEffectiveConfigPath` run completes; 9 new fields present with defaults |
| Python suites | `test_config_keys`, `test_metadata_contract`, completed/trust/validation suites, `test_settings_risk_policy_rules` (if 1.11 done), webview inventory + settings suites -- all via `apps\desktop\runtime\Python\python.exe -m unittest` |
| JS syntax | `node --check` on both touched JS files |
| Summaries | `refresh_summaries --paths <changed sources>` |
| Change packet | `validate_changes --require-worktree-coverage` (report packet id + coverage in the final response) |

Behavioral self-checks the agent CAN run (fixture-level, not real media): the live synthetic case in
section 10 case 5 proves the full invoke path against the bundled ffmpeg.

Operator-run, REQUIRED before section 7 sign-off (the agent must list these verbatim in its final response
and must NOT claim the feature is done without them):
1. Real encode, `EnableQualityVerification = $true`, defaults (`warn_only`): confirm a normal encode
   publishes, the Completed page row shows the quality score, sidecar contains `quality_verification`, and
   wall-clock overhead of the sampled run is acceptable (record it).
2. Deliberately bad encode: set `QualityFailAction = 'block_review'` and force a visibly bad encode (e.g.
   temporarily set `FallbackCpuQuality`/`VideoQuality` to the worst quality value, or use a test library
   profile) on a disposable source; confirm the run records `ENCODE_QUALITY_BELOW_FLOOR`
   (operator_required, non-retryable), the output is NOT published, no file appears in the output root or
   PendingServerPush, and the failure surfaces in the failure report with the suggested action.
3. One remux-route file: confirm no quality stage runs and nothing changed in remux behavior.
4. One 4K/10-bit (HDR if available) encode with verification on: confirm a sane (non-garbage) score --
   this exercises the 10-bit pixel-format and scale/fps alignment paths.
5. `python -m mediapipeline.tools.dev.ai_guardrail` preflight/postflight pair.
6. WebView settings smokes per AGENTS.md section 5 settings row
   (`ops\scripts\smoke\Test-WebViewSettings*`, `Test-LocalApiLifecycleContractSmoke.ps1`).

---

## 13. docs/SESSION.md scope block template (add before editing)

```
## Objective quality verification (VMAF/SSIM/PSNR) 2026-06-DD (operator-approved; plan: docs/implementation/objective-quality-verification-plan.md)

AGENTS.md section 7 (encode acceptance gating, settings schema, publish adjacency). NOT self-certified;
operator real-media rung required (plan section 12).

In-scope files:
- NEW ops/pipeline/engine/verify/quality.ps1; ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1
- ops/pipeline/engine/config/{config_keys,config_schema,default_values,choice_registry,runtime_config}.ps1
- ops/pipeline/config/schemas/media_pipeline_config.schema.json; MediaPipeline_config_template.psd1; profiles/Default.psd1
- ops/pipeline/engine/shared/failure_codes.ps1; ops/pipeline/engine/failures/failure_state.ps1
- ops/pipeline/entrypoints/MediaPipeline/encode.ps1; ops/pipeline/engine/process/pipeline_processing.ps1
- ops/pipeline/engine/publish/publish_completion.ps1; ops/pipeline/engine/paths/output_evidence.ps1
- src/mediapipeline/core/kernel/{config_key_order,config_key_groups}.py; src/mediapipeline/contracts/config.py
- src/mediapipeline/core/config/metadata_parts/<chosen part>.py; src/mediapipeline/desktop/application/settings_risk_policy_rules.py
- src/mediapipeline/core/completed/{policy,trust_fields,validation_state}.py
- apps/desktop/webview/static/assets/settingsView.builders.quality.js (NEW), settingsView.js, settingsMetadata.js;
  apps/desktop/webview/static/index.html, partials/page-settings.html
- NEW ops/pipeline/tests/Unit/Invoke-QualityVerificationChecks.ps1; targeted Python/webview test updates
- docs/inventories/{WEBVIEW_DOM_ID_INVENTORY,SETTINGS_BUILDER_COVERAGE_MATRIX,SETTINGS_KEY_OWNERSHIP_MAP}.md;
  docs/architecture/CONFIG_KEY_GLOSSARY.md; CHANGELOG.md; docs/generated/summaries mirrors; change packet
```

---

## 14. Rollback

The feature is a leaf: `EnableQualityVerification = $false` (the default) short-circuits the entire hook, so
operational rollback is "leave the key off". Code rollback is a straight revert of the change set; no data
migration, no schema version bumps, no persisted-state format changes. Sidecars/completed rows written with
`quality_verification` remain readable by older code (all readers are additive/defensive).

## 15. Trap index (the mistakes this plan exists to prevent)

- T1 module loader: register the new module in BOTH `$engineModulePaths` and `$engineModuleLoadOrder` or the
  pipeline exits FATAL at startup (module_loader.ps1:93-111).
- T2 JSON schema nested allowlists: quality keys go in top-level `properties` ONLY; the nested
  library-override/WorkerConfigOverrides objects are `additionalProperties: false` allowlists that must not
  gain these keys.
- T3 libvmaf log_path: unescaped `C:\` inside a filter graph is parsed as a filter option separator ->
  garbage/failed runs. Escape to `C\:/...`.
- T4 failure-code lists: new codes go in `Get-MediaPipelineKnownOutcomeCodes` ONLY;
  `Get-MediaPipelineKnownFailureCodes` is bidirectionally checked against classifier `return` statements.
- T5 script-state lifecycle: reset `$script:LastQualityVerification` at init (runtime_config.ps1), pre-route,
  and in the finally block, or a prior file's score leaks onto the next file's sidecar.
- T6 validation_state: quality fields are passthrough only; feeding them into `unavailable_reasons` or
  `status_state` would flip every historical/disabled-feature row to `validation-needed`.
- T7 input ordering: distorted stream is input 0 / left label, reference is input 1 / right label for
  libvmaf, ssim, AND psnr. Reversed inputs still produce a number -- a silently wrong one.
- T8 fail-open: only a successfully measured score below `QualityFailThreshold` with
  `QualityFailAction = 'block_review'` may block. Tool error/timeout/stop NEVER blocks.
- T9 ordered parity: the 9 keys must sit at the SAME relative position (after
  `OutputValidationDurationToleranceSeconds`) in every ordered surface; two checks assert sequences, not sets.
- T10 thresholds `<= 0` disable a tier -- guard before comparing, or `score < 0` can never fire and
  `score < 90` fires when the operator zeroed the warn tier.
