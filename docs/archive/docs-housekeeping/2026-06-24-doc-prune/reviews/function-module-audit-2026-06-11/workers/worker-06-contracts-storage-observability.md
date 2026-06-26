# Worker Review: worker-06-contracts-storage-observability

## Scope

- Worker ID: `worker-06-contracts-storage-observability`
- Assigned slice: contracts, generated schemas, stage runner contracts, storage/SQLite mirror logic, observability/logging/event modules, diagnostics, failure classification, and related PowerShell support modules.
- Review mode: review-only. No code fixes, refactors, commits, media mutation, runtime-state mutation, queue mutation, settings mutation, or aggregate review-file edits.
- Required first-read set was used: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, and `docs/reviews/function-module-audit-2026-06-11/ASSIGNMENTS.md`.
- Summary compliance: generated summaries under `docs/generated/summaries/` were checked before opening assigned source files where summaries existed.
- Coverage status: partial. All assigned areas received summary review and risk searches; full source was opened for the highest-risk contracts/storage/cleanup/schema files and finding files. Several large status, telemetry, naming, diagnostics, audit, and policy files received targeted rather than exhaustive full-source review.

## Coverage Ledger

| Area | Files and symbols reviewed | Coverage | Notes |
|---|---|---|---|
| Required docs and assignment | `AGENTS.md`; current state/checklist/index; W06 assignment in `ASSIGNMENTS.md` | Complete | Established no-touch media/source boundaries, validation ladder, change-packet requirement, and assigned file list. |
| Stage contracts and generated schema | `src/mediapipeline/contracts/stage_base.py`; `stage_decide.py`; `stage_mutation.py`; `stages.py`; `schemas/stages.v1.schema.json`; `tests/python/desktop/test_stage_contracts.py` | High | Findings W06-01 and W06-08. |
| API command contracts | `src/mediapipeline/contracts/api_commands.py`; `tests/python/desktop/test_api_command_contracts.py`; `mediapipeline.core.validation.boundary.validate_api_payload` behavior checked by snippet | Targeted high-risk | Finding W06-03. |
| Source-media contracts | `source_media_models.py`; `source_media_streams.py`; targeted search for `drop_candidate` | High | Finding W06-09. |
| SQLite mirror | `src/mediapipeline/core/storage/db.py`; `state_migration.py`; `contracts.py`; `constants.py`; targeted completed-manifest context from publish/completed modules | High | Finding W06-02. |
| PowerShell storage and cleanup helpers | `ops/pipeline/engine/storage/disk.ps1`; `scratch_copy.ps1`; `state_store.ps1`; `shared/path_helpers.ps1`; `shared/temp_cleanup.ps1`; `audit/probe.ps1` | High | Findings W06-04, W06-05, W06-06, W06-07. |
| Failure state and classification | `ops/pipeline/engine/failures/failure_state.ps1`; `ops/pipeline/engine/shared/failure_codes.ps1`; `src/mediapipeline/core/failures/*` summaries and targeted source | Partial | No concrete wrong failure-code mapping found in reviewed symbols. |
| Diagnostics and observability | `src/mediapipeline/core/diagnostics/facade.py`; `policy.py`; `state_summary.py`; `core/observability/*`; `core/status/*`; `ops/pipeline/engine/observability/logging.ps1` summaries and targeted source | Partial | Bounded-read and structured-result paths looked intentional in reviewed symbols. |
| Generated schemas beyond W06 assignment list | `src/mediapipeline/contracts/schemas/config.v1.schema.json`; `risky_file_registry.v1.schema.json` summaries and targeted searches | Targeted | `config.v1.schema.json` includes `fallback_remux`; stage schema drift is isolated to `stages.v1.schema.json`. |

## Findings Summary

| ID | Severity | File | Symbol/section | Short finding |
|---|---|---|---|---|
| W06-01 | Medium | `src/mediapipeline/contracts/schemas/stages.v1.schema.json`; `src/mediapipeline/contracts/stage_decide.py` | `DecidePayload.size_guard_mode` | Generated stage schema rejects active `fallback_remux` value. |
| W06-02 | Medium | `src/mediapipeline/core/storage/db.py` | `StateDb.record_completed_job` | SQLite completed-job mirror collapses repeated `job_id` rows and can diverge from append-only JSONL. |
| W06-03 | Medium | `src/mediapipeline/contracts/api_commands.py` | rename/final-library confirmation fields | High-risk confirmations are `Any` and route validation accepts non-bool values. |
| W06-04 | Medium | `ops/pipeline/engine/storage/disk.ps1` | `Copy-FileRobocopy` | Copy helper mutates destination before an effective configured-root guard. |
| W06-05 | Medium | `ops/pipeline/engine/audit/probe.ps1` | `Clear-ProbeCache` | Probe-cache cleanup recursively deletes under a script variable without boundary proof. |
| W06-06 | Medium | `ops/pipeline/engine/shared/temp_cleanup.ps1` | `Clear-OldTempFiles` | Startup scratch cleanup recursively deletes under `$script:processingDir` without validating the processing root. |
| W06-07 | Low | `ops/pipeline/engine/storage/scratch_copy.ps1` | `Remove-EmptyScratchContainer` | Empty scratch container cleanup lacks processing-root containment proof. |
| W06-08 | Low | `src/mediapipeline/contracts/stages.py`; `src/mediapipeline/contracts/stage_mutation.py` | ingest stage contract | Ingest is mutation-capable but lacks the shared dry-run/execute confirmation contract. |
| W06-09 | Low | `src/mediapipeline/contracts/source_media_models.py`; `src/mediapipeline/contracts/source_media_streams.py` | `SourceSubtitleStream.drop_candidate` | Subtitle normalization marks every subtitle as a drop candidate by default. |

## Detailed Findings

### W06-01 - Medium - Generated stage schema rejects active `fallback_remux` size guard

- File: `src/mediapipeline/contracts/schemas/stages.v1.schema.json`; `src/mediapipeline/contracts/stage_decide.py`
- Symbol/section: `DecidePayload.size_guard_mode`
- Evidence: `stage_decide.py:42` allows `Literal["advisory", "strict", "fallback_remux", "off"]`. The generated schema at `stages.v1.schema.json:166-172` lists only `advisory`, `strict`, and `off`. `config.v1.schema.json` includes `fallback_remux`, and targeted searches show active use in decision policy and settings tests.
- Impact: A stage-runner client or validator using `stages.v1.schema.json` rejects a policy value accepted by the Python stage contract and settings schema. That is contract/schema drift in a generated wire artifact.
- Fix direction: Regenerate `stages.v1.schema.json` from `StageContractSchema.model_json_schema()` and keep the existing schema-currentness test in the validation path.
- Validation: Running `apps/desktop/runtime/Python/python.exe -m unittest tests.python.desktop.test_stage_contracts.StageContractTests.test_generated_stage_schema_is_current_and_references_all_models` fails with a diff showing generated schema includes `fallback_remux` while checked-in schema does not.

### W06-02 - Medium - Completed-job SQLite mirror collapses repeated `job_id` rows

- File: `src/mediapipeline/core/storage/db.py`
- Symbol/section: `StateDb.record_completed_job`
- Evidence: The `completed_jobs` table declares `job_key TEXT NOT NULL UNIQUE` at `db.py:151-159`. `record_completed_job` uses `job_id` as `job_key` when present at `db.py:260-265`, then upserts with `ON CONFLICT(job_key) DO UPDATE` at `db.py:270-281`. The PowerShell sidecar/manifest path writes `job_id` from `$script:CurrentJobId` (`ops/pipeline/engine/publish/sidecar.ps1:181`, `:285`), and processing sets `$script:CurrentJobId` from source identity (`ops/pipeline/engine/process/pipeline_processing.ps1:247-248`).
- Impact: The authoritative completed manifest is append-only JSONL, but the SQLite mirror can retain only the latest row for repeated completions of the same source identity. UI or diagnostics that later trust the SQLite mirror can undercount or hide prior completed rows.
- Fix direction: Mirror append identity should include append order or payload hash, not only source/job identity. If deduplication is desired for a separate latest-by-source view, keep that as a second index/table instead of replacing append history.
- Validation: A temp-DB snippet that records two completed jobs with `job_id="same-source"` returns one SQLite row, with the second payload replacing the first. Add a regression test for duplicate `job_id` rows to match the JSONL manifest's append semantics.

### W06-03 - Medium - High-risk API confirmation fields are not strict booleans

- File: `src/mediapipeline/contracts/api_commands.py`
- Symbol/section: `RenameApplyCommandPayload.confirm_apply`, `RenameApplyCommandPayload.allow_outside_configured_roots`, `FinalLibraryPromoteQueueCommandPayload.confirm_promote`
- Evidence: `api_commands.py:187-211` defines rename apply confirmation and outside-root override fields as `Any`; `api_commands.py:361-363` defines final-library promote confirmation as `Any`. Other high-risk command contracts in the same file use `StrictBool`, for example failure clear at `api_commands.py:351-354`. Existing positive tests cover valid `True` values at `tests/python/desktop/test_api_command_contracts.py:302-314`, but not non-bool rejection for these routes.
- Impact: Strict JSON route handling is release-critical. Route-level validation currently accepts values such as `"true"` and `1` for these high-risk controls and relies on later handlers to fail closed. That weakens the API contract boundary and makes behavior inconsistent with adjacent strict command payloads.
- Fix direction: Type these confirmation and explicit boundary-override fields as `StrictBool | None` or a constrained strict model that preserves optional request semantics.
- Validation: A bundled-Python snippet calling `validate_api_payload("/api/rename/apply", {"confirm_apply": "true", "allow_outside_configured_roots": 1, ...})` and `validate_api_payload("/api/final-library-promotion/promote-queue", {"confirm_promote": "true"})` returned accepted payload dictionaries. Add negative contract tests asserting rejection before command dispatch.

### W06-04 - Medium - Copy helper mutates destination before an effective destination-root guard

- File: `ops/pipeline/engine/storage/disk.ps1`
- Symbol/section: `Copy-FileRobocopy`
- Evidence: `disk.ps1:352` creates `$dstDir` before destination validation. `disk.ps1:361` validates destination with `Test-MediaPipelinePathBoundarySafe -Path $Destination -Root $dstDir -AllowMissingLeaf`, which checks the destination against its own parent rather than an independently configured scratch/output/pending root. `disk.ps1:369` then creates `.mediapipeline-staging`.
- Impact: If a caller passes an unsafe or out-of-policy destination, the helper can create the destination parent before rejection and does not prove the destination is inside an allowed configured root. Current callers often compute destinations, but the reusable helper's guard is not sufficient for the source/scratch/output boundary.
- Fix direction: Accept or resolve an explicit allowed destination root, validate the destination against that root before any `CreateDirectory`, then create the destination parent and staging directory.
- Validation: Add a PowerShell test that calls the helper with a destination outside the configured output/scratch root and asserts rejection plus no created parent directory or `.mediapipeline-staging`.

### W06-05 - Medium - Probe cache cleanup lacks a root boundary check

- File: `ops/pipeline/engine/audit/probe.ps1`
- Symbol/section: `Clear-ProbeCache`
- Evidence: `probe.ps1:86-90` checks only that `$script:ProbeCacheRoot` is set and exists, then pipes all children to recursive `Remove-Item`. The audit entrypoint normally sets the variable to a `ProbeCache` directory under the audit report root, but the helper itself does not prove containment or the expected leaf before deleting.
- Impact: A misconfigured probe-cache root can recursively delete unrelated files under that directory. This is audit tooling, but it is still a destructive cleanup path and should fail closed.
- Fix direction: Validate the cache root with the existing path-boundary helper against the expected audit/state cache root and require the expected `ProbeCache` leaf before deleting children.
- Validation: Add a PowerShell test that points `$script:ProbeCacheRoot` at an external temp directory with children and asserts cleanup refuses to delete.

### W06-06 - Medium - Startup temp cleanup lacks processing-root validation

- File: `ops/pipeline/engine/shared/temp_cleanup.ps1`
- Symbol/section: `Clear-OldTempFiles`
- Evidence: `temp_cleanup.ps1:11-20` deletes matching old temp files and recursively deletes old `src_*` directories under `$script:processingDir`. It does not validate that `$script:processingDir` is the intended `LocalIncoming/Processing` scratch root or inside `LocalBase`.
- Impact: Normal startup code sets the processing directory, but this cleanup helper trusts a script variable and performs recursive deletion. If configuration or dot-sourcing context is wrong, it can remove unrelated `src_*` directories.
- Fix direction: Resolve `$script:processingDir`, validate it against the expected local processing root before enumeration, and fail closed if the root is blank, missing, a drive root, or outside the configured scratch tree.
- Validation: Add a PowerShell test with `$script:processingDir` pointed at an external temp directory containing an old `src_*` folder and assert cleanup refuses to delete it.

### W06-07 - Low - Empty scratch container cleanup lacks processing-root containment

- File: `ops/pipeline/engine/storage/scratch_copy.ps1`
- Symbol/section: `Remove-EmptyScratchContainer`
- Evidence: `scratch_copy.ps1:49-54` resolves the processing root and candidate parent, rejects equality with the processing root and non-`src_` leaves, then removes the empty parent. It does not prove the parent is a child of `$script:processingDir`.
- Impact: Current callers pass paths produced by `Get-ScratchInputPath`, so reachable risk appears limited. As a reusable helper, an unexpected path can remove an unrelated empty `src_*` directory outside the pipeline processing tree.
- Fix direction: Require `Test-MediaPipelinePathIsEqualOrChild` or equivalent containment proof that the parent is under `$script:processingDir` before removal.
- Validation: Add a unit test with an external empty `src_*` directory and assert it remains after calling the helper with a child path.

### W06-08 - Low - Ingest is mutation-capable but lacks the shared mutation contract

- File: `src/mediapipeline/contracts/stages.py`; `src/mediapipeline/contracts/stage_mutation.py`
- Symbol/section: `StageName.ingest`, `IngestPayload`
- Evidence: `stages.py:108-114` marks ingest as `mutation_capable=True`. `stage_mutation.py:12-15` defines `IngestPayload` with `intent: Literal["copy_to_scratch"]`, not the shared `MutationIntent = Literal["dry_run", "execute"]` in `stage_base.py:12`. Other mutation-capable payloads include execute confirmations, for example publish at `stage_mutation.py:109-115` and rename at `stage_mutation.py:149-155`.
- Impact: If ingest is enabled in an entrypoint or invoked through a generic stage runner, the mutation contract does not expose the same dry-run/execute safety boundary as transcode, subtitle, audio, publish, drain, and rename stages.
- Fix direction: Add dry-run/execute semantics and confirmation for ingest, or encode an explicit disabled/exempt status so generic mutation dispatch cannot execute it by accident.
- Validation: Extend stage-contract tests to assert every mutation-capable stage supports dry-run/execute plus execute confirmation, or records a deliberate and enforced exception.

### W06-09 - Low - Subtitle normalization marks every subtitle as a drop candidate

- File: `src/mediapipeline/contracts/source_media_models.py`; `src/mediapipeline/contracts/source_media_streams.py`
- Symbol/section: `SourceSubtitleStream.drop_candidate`, `subtitle_stream`
- Evidence: `source_media_models.py:114-127` sets `drop_candidate: bool = True`. `source_media_streams.py:146-159` builds every subtitle stream with passthrough/convert/burn candidate flags but never overrides `drop_candidate`. A targeted search found no other `drop_candidate` use in `src/mediapipeline/contracts`.
- Impact: The normalized source-media contract can mark preserved or convertible subtitles as drop candidates. Current reviewed assigned files did not show a downstream consumer, so this is a contract correctness risk rather than an observed publish bug.
- Fix direction: Define the intended policy and either set `drop_candidate=False` when passthrough, convert, or burn is true, or remove/rename the field if it is not active decision input.
- Validation: Add contract tests for representative text and image subtitle codecs that assert candidate flags match the subtitle preservation policy.

## Test Coverage Gaps

- Stage schema currentness test exists and currently fails; this should be part of the normal validation gate after schema edits.
- No negative API contract tests prove non-bool rename/final-library confirmation values are rejected at route validation.
- SQLite mirror tests cover duplicate output paths without `job_id`, but do not cover duplicate `job_id` rows even though sidecars write source-identity job IDs.
- No PowerShell boundary tests were found for `Copy-FileRobocopy` refusing an unsafe destination before creating directories.
- No PowerShell boundary tests were found for `Clear-ProbeCache`, `Clear-OldTempFiles`, or `Remove-EmptyScratchContainer` under misconfigured roots.
- Stage mutation tests cover publish/rename confirmation paths but not ingest's mutation-capable exception.
- Source-media subtitle contract tests do not assert `drop_candidate` semantics for text/image subtitle streams.

## Boundary Risks

- Backend/media safety boundary: findings W06-04 through W06-07 are cleanup/copy helper boundaries. None were exploited or mutated during review; they are fail-closed gaps if variables or callers are wrong.
- Strict JSON command boundary: W06-03 shows route contract drift for high-risk confirmations even though downstream handlers may reject later.
- JSON/schema compatibility boundary: W06-01 shows generated stage schema drift from Python contracts and settings schema.
- SQLite mirror boundary: W06-02 shows the optional mirror can diverge from authoritative append-only JSONL history.
- Subtitle preservation boundary: W06-09 is a contract accuracy risk that should be addressed before downstream policy consumes `drop_candidate`.

## Files Reviewed With No Findings

- `ops/pipeline/engine/storage/state_store.ps1`
- `ops/pipeline/engine/shared/path_helpers.ps1`
- `ops/pipeline/engine/paths/path_capability.ps1`
- `ops/pipeline/engine/observability/logging.ps1`
- `ops/pipeline/engine/audit/rerun_source_identity.ps1`
- `src/mediapipeline/contracts/stage_base.py`
- `src/mediapipeline/contracts/stage_probe.py`
- `src/mediapipeline/contracts/verification.py`
- `src/mediapipeline/contracts/source_media.py`
- `src/mediapipeline/contracts/source_media_adapters.py`
- `src/mediapipeline/contracts/source_media_derived.py`
- `src/mediapipeline/contracts/source_media_values.py`
- `src/mediapipeline/contracts/config_coercion.py`
- `src/mediapipeline/contracts/config_defaults.py`
- `src/mediapipeline/contracts/config_schema_extras.py`
- `src/mediapipeline/contracts/config_validators.py`
- `src/mediapipeline/contracts/height_tolerance.py`
- `src/mediapipeline/contracts/pipeline_plan.py`
- `src/mediapipeline/contracts/runtime_evidence.py`
- `src/mediapipeline/core/storage/state_migration.py`
- `src/mediapipeline/core/failures/cleanup_service.py`
- `src/mediapipeline/core/failures/facade.py`
- `src/mediapipeline/core/diagnostics/open_policy.py`
- `src/mediapipeline/core/observability/status_files.py`
- `src/mediapipeline/core/status/active_jobs.py`
- `src/mediapipeline/core/status/errors.py`
- `src/mediapipeline/core/status/file_io.py`
- `src/mediapipeline/core/status/readers.py`

## Files Marked Out Of Scope

- `ops/pipeline/engine/process/pipeline_processing.ps1` was referenced only to establish the source of `$script:CurrentJobId` for W06-02. It was not otherwise reviewed as an assigned file.
- `ops/pipeline/engine/publish/sidecar.ps1` and `src/mediapipeline/core/completed/service.py` were referenced only for completed-manifest and sidecar context for W06-02.
- `ops/pipeline/engine/policy/folder_policy.ps1` and `ops/pipeline/config/schemas/media_pipeline_folder_policy.schema.json` show related `size_guard_mode` policy surface, but they are outside this W06 assigned source list and were not counted as W06 findings.
- `src/mediapipeline/contracts/schemas/config.v1.schema.json` and `src/mediapipeline/contracts/schemas/risky_file_registry.v1.schema.json` received targeted generated-schema checks because the user scope mentioned generated schemas, but only `stages.v1.schema.json` was listed in the W06 assignment file.

## Incomplete Coverage

- Full-source review remains incomplete for large or lower-risk assigned files that received summary plus targeted risk-search coverage only: `ops/pipeline/engine/audit/policy.ps1`, `audit/progress.ps1`, `audit/reports.ps1`, `audit/scanner.ps1`, `ops/pipeline/engine/naming/destination_plan.ps1`, `movie_cleanup.ps1`, `naming.ps1`, `rename_overrides.ps1`, `tv_parsing.ps1`, `ops/pipeline/engine/paths/effective_settings.ps1`, `library_profiles.ps1`, `output_evidence.ps1`, `output_path_planning.ps1`, `ops/pipeline/engine/shared/executable_resolution.ps1`, `failure_codes.ps1`, `media_constants.ps1`, `native.ps1`, `native_process_contracts.ps1`, `source_identity.ps1`, `versioning.ps1`, `src/mediapipeline/contracts/config.py`, `decision_policy.py`, `lifecycle.py`, `src/mediapipeline/core/audit/*`, `src/mediapipeline/core/diagnostics/policy.py`, `state_summary.py`, `src/mediapipeline/core/failures/policy.py`, `retry_state.py`, `file_io.py`, `markers.py`, `src/mediapipeline/core/observability/artifact_freshness.py`, `logging.py`, `runtime_outcomes.py`, `status_policy.py`, `src/mediapipeline/core/status/eta.py`, `events.py`, `facade.py`, `ffmpeg_progress.py`, `presentation*.py`, `progress.py`, `service.py`, `snapshot_runner.py`, `summary*.py`, and `src/mediapipeline/core/telemetry/*`.
- No assigned file was intentionally skipped entirely. The skipped portion is exhaustive full-source/symbol-level review for the files listed above.
- No tests were added or source files changed. Validation snippets used the bundled Python and temporary directories only.
