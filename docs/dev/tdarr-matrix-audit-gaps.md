# TDARR Matrix Audit Tool — Gap Analysis and Remediation Plan

- Date: 2026-06-07
- Author: code-agent review (read-only inspection; no code changed)
- Scope: the new (untracked) TDARR Matrix test/audit tool
- Status: proposed; not yet approved for implementation

## Components reviewed

| Layer | File |
| --- | --- |
| Test-library generator | `src/mediapipeline/tools/dev/materialize_tdarr_test_library.py` |
| Audit / sample-run harness | `src/mediapipeline/tools/dev/tdarr_matrix_audit.py` |
| Backend command policy + service | `src/mediapipeline/core/diagnostics/tdarr_matrix_audit.py` |
| Facade adapter | `src/mediapipeline/core/diagnostics/tdarr_matrix_audit_facade.py` |
| Route contract | `src/mediapipeline/desktop/api/contract_command.py` (`/api/diagnostics/tdarr-matrix-audit`) |
| UI | `apps/desktop/webview/static/assets/diagnosticsView.js` |
| Tests | `tests/python/tooling/test_tdarr_matrix_audit.py`, `tests/python/tooling/test_materialize_tdarr_test_library.py`, `tests/python/desktop/test_service_tdarr_matrix_audit.py` |

Wiring is sound: route, services mixin, and facade are all registered, and run
roots are correctly fenced under `TdarrMatrixRuns`
(`assert_allowed_run_root`, `tdarr_matrix_audit.py:333`). The gaps below are in
behavior, robustness, and coverage — not in the command plumbing.

## Summary

| ID | Title | Severity | Class | Status |
| --- | --- | --- | --- | --- |
| G1 | Outer run timeout under-budgeted (ignores prepare-evidence) | High | Defect | Done 2026-06-07 (increment 1) |
| G2 | Bucket list drift — new bucket silently never sampled | High | Defect | Done 2026-06-07 (increment 1) |
| G3 | No backend single-flight guard (concurrent runs collide) | High | Defect | Not a gap - already mitigated (facade lock); regression test added 2026-06-07 |
| G4 | No run-root retention (unbounded `TdarrMatrixRuns` growth) | Medium | Operational | Done 2026-06-07 (increment 5, opt-in) |
| G5 | Tool cannot bootstrap its own library | Medium | Operational | Done 2026-06-07 (increment 4) |
| G6 | Silent catch-all bucket (unknown codec to `legacy-video`) | Medium | Coverage | Done 2026-06-07 (increment 3) |
| G7 | Distribution skew; bucket names overpromise codec coverage | Low | Coverage | Done 2026-06-07 (increment 5, documented) |
| G8 | Source-hash integrity off on report/strict path | Medium | Coverage | Done 2026-06-07 (increment 3) |
| G9 | Strict gate is static-only; audio-only pass-through is warning-only | Medium | Policy | Resolved 2026-06-07 (operator chose advisory + documented; no behavior change) |
| G10 | Path-containment allowlist (roots + keys) can drift | Low | Coverage | Done 2026-06-07 (increment 5) |
| G11 | Untested code paths (worker-result, prepare-evidence, progress) | Medium | Tests | Done 2026-06-07 (increment 2) |

### Implementation log

- 2026-06-07, increment 1: G1 + G2 landed in
  `src/mediapipeline/core/diagnostics/tdarr_matrix_audit.py`
  (`TDARR_MATRIX_AUDIT_BUCKET_COUNT`, `TDARR_MATRIX_AUDIT_RUNNER_TIMEOUT_MARGIN_SECONDS`,
  `tdarr_matrix_audit_runner_timeout`; run timeout now derived, configured value kept as a
  floor). Tests added in `tests/python/desktop/test_service_tdarr_matrix_audit.py`
  (timeout worst-case invariant, report-floor raise, bucket-count/series sync); smoke
  timeout assertion updated 6000 -> 7500. Validation: 16/16 unittest pass via bundled
  Python. Summary refreshed for the edited source.
- 2026-06-07, increment 2: G11 test-only coverage added (no source change).
  `tests/python/tooling/test_tdarr_matrix_audit.py`: `command_failure_finding`
  (timeout / nonzero / clean / None), and `audit_worker_result` branches (non-audio
  success, audio-only warning, missing result, timeout-without-result, already-processed
  skip, classified failure, unclassified failure). `tests/python/tooling/test_materialize_tdarr_test_library.py`:
  `diagnostic_bucket` for mjpeg-large / av1-vp-modern / legacy-video, mjpeg-over-container
  precedence, and the silent catch-all (documents the G6 gap until G6 makes it a finding).
  `tests/python/desktop/test_service_tdarr_matrix_audit.py`: progress-payload status
  transitions (complete / warning / blocked / error). Validation: 21/21 unittest pass;
  py_compile clean. Note: the helper was named `_make_outcome`, not `_outcome`, because
  `unittest.TestCase` reserves `self._outcome` during a run.
- 2026-06-07, increment 3: G6 + G8.
  G6: `materialize_tdarr_test_library.py` now exposes `classify_bucket(medium, video_codec,
  container) -> (bucket, is_fallback)`; `diagnostic_bucket` delegates to it (bucket
  assignment unchanged). `tdarr_matrix_audit.py` adds `audit_bucket_classification` (warning
  findings `bucket_classification_fallback` for catch-all codecs and `bucket_classification_drift`
  for recorded-vs-recomputed mismatch), wired into both `audit_existing_library` (report) and
  `command_run_samples`. Warning severity, so it surfaces without failing the strict gate.
  G8: report and strict-report presets gain `hash_sources: True`; `tdarr_matrix_audit_arguments`
  now appends `--hash-sources` in report mode (smoke/matrix unaffected; run-samples already
  hashes). Tests added: `classify_bucket` fallback, `audit_bucket_classification` unmapped
  codec, and `--hash-sources` preset assertions. Validation: 23/23 unittest pass; py_compile
  clean; integration check on the real 4632-row library = 0 hash findings, 0 bucket findings
  (all current codecs mapped, sources match manifest SHAs). Summaries refreshed for the 3
  edited sources.
- 2026-06-07, increment 4: G5 + G3 correction + change packet.
  G3 re-examined: NOT a gap. The facade `DiagnosticsTdarrMatrixAuditFacadeMixin.run_tdarr_matrix_audit`
  already acquires `self._diagnostics_command_lock` (a real `threading.Lock()` set in
  `src/mediapipeline/desktop/application/facade.py`) non-blocking and returns an unavailable
  result when busy. The original G3 finding missed this. Added two regression tests
  (busy-blocked, lock-released-after-success) in
  `tests/python/desktop/test_service_tdarr_matrix_audit.py`.
  G5: the service mixin now checks for the materialized base manifest before launching and
  returns `_tdarr_matrix_missing_library_result` (returncode 2, actionable message naming
  `materialize_tdarr_test_library`) without spawning a subprocess. Existing service test
  updated to create the base manifest; new missing-library test added.
  Change packet `ops/release/changes/unreleased/MP-CHANGE-2026-0607-020.json` created covering
  G1, G2, G5, G6, G8, G11. Validation: 26/26 unittest pass; py_compile clean; summaries
  refreshed; `change_control.validate_changes` clean for this packet (only unrelated
  `MP-CHANGE-2026-0605-010` fails, missing `date_completed`).
- 2026-06-07, increment 5: G4 + G7 + G10 (all in `tdarr_matrix_audit.py` /
  `materialize_tdarr_test_library.py`).
  G4: added `discover_run_roots` and `prune_run_roots(runs_root, keep_last, dry_run)` plus
  opt-in `--keep-last` / `--prune-dry-run` on the run-samples CLI. Safe by default: the
  UI/backend wrapper never passes `--keep-last`; `keep_last` must be >= 1 (the newest/current
  run is never deleted); only sentinel-marked dirs directly under TdarrMatrixRuns are eligible;
  non-sentinel dirs are never touched; dry-run previews without deleting.
  G7: documented the container-before-codec precedence and the resulting container-stress skew
  in the `classify_bucket` docstring (no sampling-behavior change; sub-bucketing left as a
  future option).
  G10: extracted the path-containment scan roots to a single `CONTAINMENT_SCAN_SUBDIRS`
  constant with a maintenance note tying it (and `CONTAINMENT_PATH_KEYS`) to evidence-writing
  code; added a test that asserts every declared root is actually scanned.
  Tests added: `prune_run_roots` (dry-run, real delete keeps newest, non-sentinel guard,
  keep_last<1 rejected) and `audit_path_containment` over all declared roots. Validation:
  28/28 unittest pass; py_compile clean; summaries refreshed; change packet
  MP-CHANGE-2026-0607-020 updated to cover G4/G7/G10.
- 2026-06-07, increment 6: G9 resolved per operator decision (advisory + documented). No
  behavior change; added explanatory comments at the `strict-report` preset
  (`core/diagnostics/tdarr_matrix_audit.py`) and the `audio_only_processed_successfully`
  finding (`tools/dev/tdarr_matrix_audit.py`). Validation: 28/28 unittest pass; py_compile
  clean; summaries refreshed.
- Remaining: none. All gaps (G1-G11) are addressed (G3 was a non-gap; G9 resolved as a
  documented advisory). Any future promotion of audio-only success to a hard failure is a
  separate media-policy change requiring AGENTS.md §7 operator validation.

Severity key: High = can produce wrong results or kill a valid run; Medium =
silent coverage loss or operational debt; Low = clarity / future-proofing.

---

## Concrete defects

### G1 — Outer run timeout is under-budgeted

- Location: presets `tdarr_matrix_audit.py:33-50` (`runner_timeout_seconds`);
  `prepare_pipeline_evidence` runs 3 PowerShell commands each capped at
  `prepare_timeout_seconds` (`tdarr_matrix_audit.py` dev harness `:583`).
- Symptom: `runner_timeout_seconds` does not include prepare-evidence time.
  Worst case:
  - Smoke: cap 6000 s; work approx 1800 (prepare = 3 x 600) + 6 x 900 = 7200 s.
  - Matrix: cap 55200 s; work approx 1800 + 30 x 1800 = 55800 s.
  The `run_capture` wrapper can kill a still-running, healthy run and report a
  false `timed_out`.
- Fix: derive `runner_timeout_seconds` instead of hard-coding it:
  `(3 * prepare_timeout_seconds) + (samples_per_bucket * len(BUCKET_ORDER) *
  sample_timeout_seconds) + margin`. For report/strict the sample term is 0.
  Add a small fixed margin (for example 300 s) for audit/IO overhead.
- Validation: unit test asserting, for each preset, `runner_timeout_seconds >=`
  the derived worst case. No real run required.

### G2 — Bucket list drift: a new bucket is silently never sampled

- Location: generator `BUCKET_SERIES`
  (`materialize_tdarr_test_library.py:27`), audit `BUCKET_ORDER`
  (`tdarr_matrix_audit.py:35`), test `BUCKETS`. `select_sample_rows`
  (`tdarr_matrix_audit.py:307-330`) iterates only `BUCKET_ORDER`.
- Symptom: add a 7th bucket to the generator and its files are never drawn into
  smoke/matrix; nothing warns. The "30-File Matrix" silently misses a category.
- Fix: make one list the single source of truth and derive the others, or add a
  contract test asserting `set(BUCKET_SERIES) == set(BUCKET_ORDER)`. Optionally
  emit an audit finding when a manifest bucket is absent from `BUCKET_ORDER`.
- Validation: new unit test (no real run).

### G3 — No backend single-flight guard

- CORRECTION 2026-06-07: this is NOT a gap. The facade already guards concurrency via
  `self._diagnostics_command_lock` (a `threading.Lock()` in
  `src/mediapipeline/desktop/application/facade.py`), acquired non-blocking in
  `DiagnosticsTdarrMatrixAuditFacadeMixin.run_tdarr_matrix_audit`, returning an unavailable
  result when busy. The original analysis below missed the facade lock. Regression tests were
  added; no behavior change was needed.
- Location: concurrency is enforced only in the browser
  (`tdarrMatrixAuditInFlight`, `diagnosticsView.js:3,49`).
  `run_tdarr_matrix_audit` (`tdarr_matrix_audit.py:334`) has no lock.
- Symptom: two API/browser sessions can run at once. Two report/strict runs
  overwrite the same base-library `manifests/audit/*`; two run-samples started in
  the same second collide on the `run-YYYYMMDD-HHMMSS` root (`FileExistsError`
  surfaced as a generic exception result).
- Fix: add a backend single-flight guard in the service mixin (process-level
  lock / sentinel) that returns a clean "already running" `CommandResult` instead
  of racing. Reuse the existing `tdarr_matrix_audit_unavailable_result` shape.
- Validation: unit test that a second concurrent call returns the busy result;
  confirm run-id uniqueness (consider adding a short random suffix to the run id).

---

## Operational gaps

### G4 — No run-root retention

- Location: `command_run_samples` (`tdarr_matrix_audit.py:1122`) creates
  `TdarrMatrixRuns/run-*` per invocation (hardlinked sample tree + logs); nothing
  prunes it.
- Symptom: unbounded growth under `LocalBase/Scratch/TestLibraries/TdarrMatrixRuns`.
- Fix: add `--keep-last N` (default e.g. 5) that prunes oldest sentinel-marked
  run roots after a successful run. Must reuse the existing sentinel guard
  (`AUDIT_RUN_SENTINEL`) and `assert_allowed_run_root` so deletion stays fenced
  under the runs root. Dry-run first; never delete a dir lacking the sentinel.
- Validation: unit test on the retention selector against fake run dirs; confirm
  non-sentinel dirs are never removed. Media-safety note: deletion is limited to
  isolated test-run roots only.

### G5 — Tool cannot bootstrap its own library

- Location: all four presets read the base
  `TdarrMatrix/manifests/materialized_library.csv`. Missing input gives critical
  `required_input_unreadable` (report/strict) or `FileNotFoundError` in
  `load_manifest_rows` (`tdarr_matrix_audit.py:1125`, surfaced as a generic
  exception result for run-samples).
- Symptom: on a fresh checkout, cleaned scratch, or after `--rebuild`, every
  button fails with an unclear error and no remediation hint.
- Fix (pick one):
  - Add a 5th action/button "Materialize Library" that runs
    `materialize_tdarr_test_library` with `--write-config`; or
  - Detect the missing base library and return a clear, actionable
    `CommandResult` telling the operator which command to run.
- Validation: unit test for the missing-library branch returning the actionable
  result.

---

## Coverage and policy gaps

### G6 — Silent catch-all bucket

- Location: `diagnostic_bucket` returns `legacy-video` for any unrecognized
  codec (`materialize_tdarr_test_library.py:125`).
- Symptom: today all 14 inventory codecs map cleanly, but a new label
  (`hevc`, `prores`, `vp9.2`, ...) silently mis-buckets with no finding.
- Fix: add an audit check that every distinct inventory `video_codec` /
  `container` maps to an explicit bucket rule; emit a `warning` finding (code
  e.g. `bucket_classification_fallback`) when the catch-all is hit. Keep the
  catch-all as a safety net, but make it visible.
- Validation: unit test feeding an unknown codec and asserting the finding.

### G7 — Distribution skew; bucket names overpromise codec coverage

- Location: container check precedes codec checks
  (`materialize_tdarr_test_library.py:108-125`). This is intended (confirmed by
  `test_materialize_tdarr_test_library.py:97`: h264-in-avi to container-stress).
- Symptom (live counts, per inventory row): container-stress 1340,
  legacy-video 429, av1-vp-modern 195, mjpeg-large 185, h264-h265-direct 130,
  audio-only 37. Codec buckets only ever see mkv/mp4; h264/av1/vp9 inside stress
  containers file as container-stress, so a 5-per-bucket matrix under-samples
  real codec x container combinations.
- Fix (optional / design decision): document the precedence explicitly in the
  tool docstring, or add codec-aware sub-buckets within container-stress so the
  matrix samples codec diversity inside stress containers. No correctness bug.
- Validation: documentation + (if sub-buckets added) selection unit test.

### G8 — Source-hash integrity off on the report/strict path

- Location: `audit_source_hashes` runs only in run-samples
  (`tdarr_matrix_audit.py:1151,1163`); `command_report` skips it unless
  `--hash-sources`, which the backend wrapper never passes.
- Symptom: report/strict never verify the SHA-256 the manifest already carries —
  the cheapest non-destructive integrity check is unused on the default path.
- Fix: have the backend pass `--hash-sources` for the report and/or strict
  presets (it is non-destructive). Consider a size cap or sampling for the full
  4632-row base library to bound runtime; full hashing is acceptable for strict.
- Validation: existing `audit_source_hashes` unit test covers detection; add a
  preset-argument test asserting `--hash-sources` is present for the chosen
  preset(s).

### G9 — Strict gate is static-only; audio-only pass-through is warning-only

- RESOLUTION 2026-06-07 (operator decision): keep audio-only success as an advisory
  `warning` (no behavior change) and document that the strict gate is a static config /
  queue-preview / source-hash gate, not a media-policy gate. Documented in code at the
  `strict-report` preset (`core/diagnostics/tdarr_matrix_audit.py`) and at the
  `audio_only_processed_successfully` finding (`tools/dev/tdarr_matrix_audit.py`). Option (a)
  below (promote to error) was explicitly not chosen and remains a future media-policy change
  requiring real-media validation.
- Location: strict-report preset is mode `report`, `report_only=False`, no
  `--hash-sources` (`tdarr_matrix_audit.py:51-59`). `audio_only_processed_successfully`
  is severity `warning` (`tdarr_matrix_audit.py:823`); strict fails only on
  `FAIL_SEVERITIES = {critical, error}` (`tdarr_matrix_audit.py:43`).
- Symptom: the "Strict Report Gate" processes no media and will not fail if an
  audio-only sample is processed/encoded — so it cannot gate the
  "audio-only must be rejected" media policy (if that is the intended policy).
- Fix: decide the intended policy, then either (a) raise audio-only-success to
  `error` so strict fails, gated behind a config/flag; or (b) document that
  strict is a static config + queue-preview gate and is not a media-policy gate.
  Tie any severity change to the actual media-policy SSOT before changing it.
- Validation: AGENTS.md section 7 area — do not self-certify. If severity
  changes, operator real-media validation is required.

### G10 — Path-containment allowlist can drift

- Location: `audit_path_containment` scans 4 fixed roots and the fixed
  `CONTAINMENT_PATH_KEYS` set (`tdarr_matrix_audit.py:744-771`).
- Symptom: new evidence dirs or new path-bearing keys silently escape the
  escape-check.
- Fix: derive the scanned roots/keys from a shared contract (or assert them
  against the queue/completed/pending DTO key set) so additions are caught.
  Lower priority; current set matches today's evidence layout.
- Validation: unit test that a path under a newly added evidence root is scanned.

---

## Test-coverage gaps

### G11 — Untested code paths

Current tests cover: manifest load, queue-snapshot findings, exit-code
strictness, sample-selection balance, materialize/rebuild guard, command
builders, hash + containment findings, and the service presets/result shape.

Not covered (add unit tests):

- `audit_worker_result` branches: success, audio-only warning, already-processed
  skip, classified vs unclassified failure (`tdarr_matrix_audit.py:791`).
- `prepare_pipeline_evidence` / `command_failure_finding` for timeout and
  nonzero exit.
- `tdarr_matrix_audit_progress_payload` step/percent/status logic
  (`core/diagnostics/tdarr_matrix_audit.py:161`).
- Generator-vs-audit bucket-list sync (covers G2).
- Preset timeout-budget invariant (covers G1).
- `diagnostic_bucket` for `mjpeg-large`, `av1-vp-modern`, `legacy-video`, and the
  catch-all (the existing generator test only checks direct/container/audio,
  `test_materialize_tdarr_test_library.py:96-98`).

---

## Suggested sequencing

1. Cheap, self-contained, no behavior risk (do first):
   G1 (timeout budget), G2 (bucket-sync test), G11 (unit tests),
   G6 (catch-all finding).
2. Robustness/operational:
   G3 (single-flight), G4 (retention), G5 (bootstrap affordance), G8 (hashing).
3. Policy / design decisions (need operator input, possibly AGENTS.md section 7):
   G9 (strict-gate semantics), G7 (sub-bucketing), G10 (allowlist source).

## Validation rung (AGENTS.md section 5)

- G1, G2, G4, G6, G10, G11: agent-side Python unit tests via
  `apps\desktop\runtime\Python\python.exe` are sufficient.
- G3, G5, G8: agent-side unit tests plus a local-API / diagnostics smoke against
  a running backend.
- G9 and any change that processes real media or alters media-policy severity:
  AGENTS.md section 7 — not self-certified; operator real-media validation
  required before sign-off.

## Notes

- This document is analysis/planning only; no source files were modified.
- Each remediation should land as its own change packet under
  `ops/release/changes/unreleased/` per AGENTS.md section 8, with summaries
  refreshed for any edited source file.
