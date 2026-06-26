# Test Coverage Rationalization - 2026-06-18

Change packet: `MP-CHANGE-2026-0618-012`

This is a docs-only rationalization pass over the current test surface. It
does not edit, move, delete, skip, or rename tests. It classifies the active
test/check files, identifies overlap candidates, and recommends consolidation
steps that preserve the project's safety posture.

This report builds on:

- `docs/ai-audits/2026-06-17-test-coverage-gap-analysis.md`
- `docs/ai-audits/2026-06-17-audit-master-registry.md`
- `docs/inventories/TEST_SUITE_SUBSYSTEM_INVENTORY.md`
- `docs/testing/TEST_COVERAGE_MATRIX.md`
- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`

## Executive Summary

The live worktree contains a broad layered suite rather than a simple
duplicate-heavy suite. Many apparent overlaps are intentional: a Python unit
test proves backend behavior, a static WebView test proves route ownership or
DOM contract, a browser smoke proves real rendering and no forbidden mutation,
a PowerShell check proves runtime script behavior, and a wrapper gives the
operator a stable command.

The useful consolidation target is therefore documentation, fixture setup, and
wrapper mapping, not deletion of assertions. The safest immediate work is to:

1. Normalize smoke-wrapper-to-module ownership documentation.
2. Mark exact same-name Python tests as review candidates, not removals.
3. Keep static/browser pairs where they prove different tiers.
4. Add missing high-risk tests before any reduction near source movement,
   FFmpeg/media policy, pending publish, command journal, strict JSON,
   close-readiness, network, or Tauri lifecycle.

## Method

Read-only analysis used:

- `rg --files`-equivalent discovery over `tests/`, `ops/pipeline/tests/`,
  `ops/scripts/smoke/`, and `ops/scripts/release/test.ps1`.
- Python AST parsing for test function names and imported `mediapipeline.*`
  modules.
- Keyword/filename classification for subsystem and proof tier.
- Regex parsing of smoke wrappers and release-gate invocations.
- Existing TESTGAP and master-registry reports as high-risk gap inputs.

The counts below are a live-worktree snapshot. The worktree already contains
other uncommitted/untracked work, including additional tests and change
packets. This report records the observed state; it does not assert that every
file is part of a clean baseline.

## Current Test Surface

Discovered files: **378** test/check files.

Python test definitions discovered by AST: **2,504**.

| Proof tier | Count | Consolidation posture |
|---|---:|---|
| Python desktop unit | 159 | Keep; main fast behavioral net. Consolidate only shared fixtures/helpers. |
| Facade/API unit | 52 | Keep; route/command safety, strict JSON, journal, and mutation guards are release-critical. |
| Python core unit | 17 | Keep; contract/domain tests are lower-level proof than desktop facade tests. |
| Python tooling | 17 | Keep; guards generated maps, summaries, naming, dependency, and packet hygiene. |
| Python integration | 3 | Keep; synthetic media-policy parity checks do not replace runtime or real-media validation. |
| Static WebView/unit | 15 | Keep when paired with browser smokes; static tests catch ownership and route drift cheaply. |
| Non-browser WebView smoke | 12 | Keep when they exercise mocked DOM states that are hard to reach in browser fixtures. |
| Browser smoke | 21 | Keep; these uniquely prove real rendering and fixture no-mutation behavior. |
| PowerShell unit | 43 | Keep; these are the only direct gates for many runtime script policies. |
| PowerShell aggregate/runtime | 4 | Keep; they compose lower-level checks or run generated-media/runtime safety proof. |
| Runtime/adversarial | 1 | Keep; `Invoke-AdversarialForceKillEncodeChecks.ps1` is unique generated-media partial-output proof. |
| Smoke wrapper | 30 | Review docs/metadata only; wrappers are stable operator entrypoints for underlying tests. |
| Release gate | 1 | Keep; `ops/scripts/release/test.ps1` is the release composition boundary. |
| Legacy PowerShell | 1 | Keep behind explicit legacy flag only; do not promote into current default validation. |
| Other `__init__`/support files | 2 | Not consolidation targets. |

## Subsystem Classification

The classifier assigns every discovered file to a dominant subsystem using
filename and content keywords. Some broad safety helpers are intentionally
classified under source/path safety because they assert no-mutation or path
boundary behavior even when their filenames mention WebView or smoke wrappers.

| Subsystem | Count | Main surfaces |
|---|---:|---|
| Source/path safety | 75 | Path boundaries, source/scratch/output safety, open allowlists, no-mutation smokes, file/folder policy. |
| Media route/audio/subtitle/FFmpeg | 44 | Route decisions, remux/encode policy, subtitle/audio settings, generated-media runtime checks, media-policy matrices. |
| Observability/diagnostics/telemetry | 42 | Status, Diagnostics, progress, command/evidence views, logs, metrics, failure reporting. |
| WebView/UI boundary | 38 | Browser/static WebView, DOM, route ownership, frontend mutation boundary, layout and navigation. |
| Local API/commands/contracts | 34 | Route contracts, strict JSON, command results, command journal, API inventories. |
| Completed/pending publish | 28 | Completed manifests, pending manifests, drain/reconciliation proof, final-library evidence. |
| Network/coordinator | 27 | Coordinator/worker lifecycle, claims, heartbeats, path mapping, crash recovery, security. |
| Tooling/release/docs hygiene | 26 | Change control, summaries, dependency maps, naming lint, release packaging, active-doc guards. |
| Config/settings | 24 | PSD1/config schema, settings preview/save, library profiles, metadata and defaults. |
| Queue/launch/schedule | 18 | Queue preview/dry-run/priority, launch readiness, schedule watcher/editor. |
| Process lifecycle/close readiness | 15 | Process spawn/control/kill, ActiveJobs, close-readiness, Tauri shell patterns. |
| Rename/naming | 2 | Dominant filename/content classification undercounts rename because many rename tests also assert path/source safety. Use `docs/inventories/RENAME_SAFETY_TEST_INVENTORY.md` as the rename owner inventory. |
| Unclassified/support | 5 | Package markers and generic support files. |

## Overlap Candidates

These are candidates for review, not deletion. The default decision is to keep
coverage until a stronger replacement exists and has run at the right
validation rung.

### Exact Duplicate Test Names

| Candidate | Files | Recommendation |
|---|---|---|
| `test_success_message_and_payload_are_stable` | `test_facade_process_audit_policy.py`, `test_facade_process_pipeline_policy.py`, `test_facade_process_rerun_policy.py` | Keep behavior assertions; consider extracting shared assertion helper if future edits touch all three. |
| Stage contract tests | `tests/python/core/contract/test_stage_contracts.py`, `tests/python/desktop/test_stage_contracts.py` | Keep both until desktop compatibility entrypoint is retired; core and desktop paths prove different import surfaces. |
| `test_git_diff_candidates_uses_three_dot_merge_base_range` | `test_marketecture_guard.py`, `tests/python/tooling/test_lint_naming.py` | Review for shared helper or single tooling-owner test; low-risk consolidation candidate. |
| `test_format_bytes_compact_uses_existing_units` | `test_facade_completed_policy.py`, `test_service_pending_publish_format.py` | Keep unless the formatting helper becomes a single public utility with direct unit coverage. |
| `test_format_active_job_summary_reports_invalid_current_contract` | `test_service_status_active_jobs.py`, `test_status_service.py` | Keep if one is compatibility coverage; otherwise candidate for targeted merge after reading both tests. |
| `test_empty_preview_fields_keep_operator_warning` | `test_facade_audit_policy.py`, `test_facade_completed_policy.py` | Keep; audit/completed warning wording can diverge safely only if both stay pinned. |
| `test_config_path_overlap_warning_reports_same_source_roots` | `test_service_config_path_warnings.py`, `test_service_config_validation.py` | Candidate for helper reuse, not assertion removal. |

### Similar File Purpose

| Candidate cluster | Why it looks overlapping | Keep despite overlap? |
|---|---|---|
| `test_maintenance_change_ledger.py`, `test_webview_maintenance_change_ledger_static.py`, `test_webview_browser_maintenance_change_ledger_smoke.py` | Same feature across backend, static WebView, and browser. | Yes. They prove route data, static markup/route ownership, and real browser behavior separately. |
| `test_application_facade_settings_patch.py`, `test_facade_settings_patch_policy.py`, `test_webview_settings_patch_smoke.py` | Settings patch appears in service/facade/WebView tiers. | Yes. Keep until settings save/preview risk decreases; source mutation/config persistence is high impact. |
| `test_stage_contracts.py` in core and desktop | Same contract name in two trees. | Yes until one import surface is intentionally removed. |
| `test_service_tdarr_matrix_audit.py` and `tests/python/tooling/test_tdarr_matrix_audit.py` | Tdarr matrix audit appears under desktop service and tooling. | Review. If one tests service facade and one tests CLI/tool behavior, keep; if both parse the same artifact, consolidate shared fixtures. |
| `test_service_dependency_atlas.py` and `tests/python/tooling/test_dependency_atlas.py` | Dependency atlas service/tooling split. | Review for helper extraction; keep separate entrypoints if one guards CLI output and one guards app service behavior. |
| `test_sample_validation_api.py` and browser sample-validation smoke | Same operator workflow. | Keep. API route shape and browser no-mutation workflow are different proof tiers. |
| Diagnostics handoff browser/static smokes | Similar text and target ownership. | Keep if one is owner-row handoff and the other browser bridge; consolidate fixture setup only. |

### Static/Browser Pairs

Static/browser pairs should generally stay. Static tests cheaply catch route,
asset, DOM, public global, and mutation-boundary drift before a browser opens.
Browser tests uniquely prove rendering, click paths, filter behavior, and
fixture no-mutation assertions.

Do not remove static tests just because browser smokes exist for:

- frontend mutation boundaries;
- Network read-only lifecycle/setup controls;
- Rename apply readiness;
- Settings patch and settings-launch handoff;
- Layout manager;
- Maintenance/Reports;
- Queue file overrides;
- Pending drain guard;
- Command evidence and selected-row detail.

### Wrapper/Module Pairs

The 30 `ops/scripts/smoke/Test-*.ps1` wrappers mostly delegate to Python test
modules. That is intentional. They are stable operator-facing commands and
should not be treated as duplicate tests.

Low-risk improvement: add or maintain wrapper metadata in smoke catalogs so
each wrapper clearly names the underlying module, proof tier, and mutation
boundary. Do not remove wrappers unless the operator-facing command is also
retired from docs and release gates.

### Repeated Fixture Assertions

Repeated fixture assertions appear in browser smokes for no forbidden POSTs,
no fixture byte mutation, and row-selection behavior. These are good
duplication when each page owns a different high-risk command surface. A safe
consolidation is shared assertion helpers in browser smoke support, not fewer
page-specific assertions.

## High-Risk Weak Coverage

| Area | Current coverage posture | Weakness | Recommendation |
|---|---|---|---|
| Source mutation / cleanup | Path tests, open allowlists, no-mutation browser smokes, release/pipeline guards. | Stale partial cleanup and single-file launch outside roots remain TESTGAP/source-safety concerns. | Add provenance/path-boundary cleanup tests and launch-route rejection tests before any consolidation near source/scratch/output movement. |
| FFmpeg/media policy | Python core route tests, integration matrices, PowerShell media checks, generated-media adversarial encode. | No automated test fully proves real FFmpeg remux/encode correctness on representative files. | Keep all synthetic tiers; require real-media validation for behavior changes. |
| Subtitles | Python subtitle helpers, PowerShell subtitle/OCR checks, settings builder tests. | Real TX3G/BDPGS/VobSub conversion and OCR output remain weak without real samples. | Do not reduce subtitle tests; add real-media/playbook evidence when subtitle policy changes. |
| Audio | Config/settings and PowerShell audio policy checks. | Multi-track/default-language runtime parity is still largely fixture/synthetic. | Keep audio config/policy tests and add parity samples before any policy change. |
| Pending publish / drain | Manifest, path, browser guard, PowerShell safety checks. | Dual-drain/global lease and final-placement proof depth remain open gaps. | Add mutex/lease or dual-process fixture tests before reducing any pending-publish coverage. |
| Queue/launch | Queue preview/dry-run/priority, Launch readiness, browser Launch/Queue smoke. | End-to-end queue to launch to completed is not smoke-exercised with real media. | Keep layered queue/launch tests; add source-root and priority/hold fail-closed tests as needed. |
| Rename | Dedicated inventory plus service/facade/UI/browser tests. | Undo-manifest reverse verification, network path rewrite, real sidecar pair, and active-pipeline lock remain gaps. | Keep all rename safety tiers; consolidate only helper duplication. |
| Command journal / strict JSON | Local API/facade tests and static WebView command-boundary tests. | Route-exception and journal persistence-degradation scenarios need explicit regression tests. | Do not reduce command/journal/strict JSON tests; add failure-path tests first. |
| Duplicate commands / in-flight UI | Process/launch duplicate guards and some browser no-post smokes. | UI stale result/double-submit behavior is uneven across panels. | Add slow/hung POST browser smokes per high-risk command before consolidation. |
| Close-readiness / active work | Unit/facade close-readiness, Tauri scaffold, lifecycle browser smoke, adversarial encode kill. | Live Tauri close dialog and broader orphan recovery remain manual or narrow. | Keep scaffold and lifecycle tests; add controlled live active-work validation for release-sensitive shell changes. |
| Network/coordinator | Broad network unit suite, security/source-policy/crash tests, Network browser smoke. | Split-brain, durable terminal acceptance, save-failure, and multi-worker churn remain high-risk gaps. | Keep network tests; add adversarial coordinator fixtures before expanding or consolidating network mode. |
| Tauri lifecycle | Rust-source scaffold tests, production-surface script, lifecycle smoke. | Clean-machine/package install and live close prompts are not covered by routine automation. | Keep static/scaffold tests; package/open/close validation remains required for launcher/package changes. |

## Consolidation Backlog

### Safe Now

- Document wrapper-to-module ownership in smoke catalogs and active inventories.
- Extract shared Python assertion helpers for repeated exact-name tests when
  future edits already touch all participating files.
- Consolidate repeated fixture setup in browser smoke support while preserving
  page-specific assertions.
- Add notes to overlap candidates instead of deleting tests.

### Only After Stronger Coverage

- Merge duplicate stage contract coverage only after the desktop compatibility
  entrypoint is intentionally retired and a core contract gate is the single
  documented owner.
- Reduce settings patch overlap only after backend preview/save, raw key
  preservation, LibraryProfiles, and browser no-mutation coverage all pass in
  the same packet.
- Reduce pending-publish overlap only after dual-drain/final-placement tests
  exist.
- Reduce network overlap only after split-brain, save-failure, path identity,
  and multi-worker churn tests exist.
- Reduce media/subtitle/audio overlap only after a rerunnable real-media
  sample matrix exists or the change is explicitly outside media behavior.

### Do Not Consolidate

- Do not remove WebView static mutation-boundary tests because browser smokes
  exist.
- Do not remove browser smokes because static tests exist.
- Do not remove PowerShell unit checks when Python tests cover similar policy;
  PowerShell remains the runtime media engine for many behaviors.
- Do not remove release gate composition or smoke wrappers as "duplicates" of
  the underlying Python modules.
- Do not reduce command journal, strict JSON, duplicate-command guard, or
  close-readiness tests unless a stronger same-rung replacement is already in
  place.

## Acceptance Criteria For Future Test Consolidation

Before any future packet removes or merges tests, it should record:

- the exact tests being removed or merged;
- the proof tier they covered;
- the replacement test, wrapper, or release gate;
- why the replacement proves the same behavior at the same or stronger rung;
- validation output for the touched subsystem;
- change-control coverage for removed paths and new/updated paths.

## Follow-Up Recommendations

1. Create a small machine-readable smoke wrapper map so docs and release
   wrappers can be checked for drift.
2. Add a focused duplicate-test-name report to tooling so future exact-name
   overlap is visible without manual AST scripts.
3. Split future work into separate packets by risk tier: docs/wrapper mapping,
   helper extraction, then high-risk missing-test additions.
4. Treat `docs/ai-audits/2026-06-17-test-coverage-gap-analysis.md` as the
   gap backlog and this report as the consolidation/rationalization layer.

## Follow-Up Implementation Status - 2026-06-18

`MP-CHANGE-2026-0618-014` implements the low-risk docs/tooling slice from the
follow-up list:

- `docs/generated/SMOKE_WRAPPER_MAP.json` records wrapper-to-module ownership,
  proof tier, boundary text, docs presence, and release layout presence.
- `docs/generated/DUPLICATE_TEST_NAMES.md` records exact duplicate Python test
  names across `tests/python` and `tests/webview`.
- `ops/scripts/release/test.ps1` checks both generated artifacts with
  `--check` as source-tree tooling guards.

Future packets remain split by risk:

- helper extraction only after reading the duplicate groups and preserving each
  proof tier;
- high-risk missing-test additions from
  `docs/ai-audits/2026-06-17-test-coverage-gap-analysis.md`, with validation
  matched to the touched source mutation, media, publish, network, command, or
  Tauri lifecycle subsystem.
