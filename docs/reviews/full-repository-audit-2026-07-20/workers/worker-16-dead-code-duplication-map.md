# Worker 16 — Dead Code and Duplication Map

## Scope and result

This worker inspected the first-party Python, WebView JavaScript, Tauri Rust, PowerShell, launcher, configuration, and test universe for unused definitions, compatibility shims, unreachable branches, byte/AST duplicates, copied policy, and previously reported dead-code candidates. It made no product-source changes and did not edit central audit ledgers.

Artifacts:

- `worker-16-dead-code-duplication-map.jsonl` — 15 structured coverage records.
- `worker-16-dead-code-duplication-map-findings.jsonl` — three schema-valid findings.
- `worker-16-dead-code-duplication-map-errors.jsonl` — 28 schema-valid command errors, expected no-match results, corrected methodology events, missing optional tooling, timeouts, and warnings.
- This file — method, findings, candidate interpretation, and validation.

The final deterministic snapshot covered 2,085 files and 38,248,956 bytes:

| Root | Files |
| --- | ---: |
| `src/` | 770 |
| `tests/` | 422 |
| `ops/` | 480 |
| `apps/` | 413 |
| **Total** | **2,085** |

Snapshot SHA-256: `5a688bf53375c2dbe9b520001bc0b977fbd8275c2fc5264b2208c11ae6c0a421`.

The digest includes path, byte size, and per-file hash. It excludes the bundled `ops/pipeline/runtime`, Cargo `target`, `node_modules`, and caches. Other agents were active in the worktree, so every formal finding is additionally bound to unchanged, clean source hashes listed in the JSONL map.

## Interpretation rule

A static candidate is not proven dead.

- **Confirmed defect** means a current clean-source behavior was reproduced or a live reader/writer contract was shown to disagree.
- **Confirmed duplication** means files or normalized definitions are identical; it does not by itself authorize deletion.
- **Static removal candidate** means the bounded repository scan found no direct reference. Dynamic imports, classic-script globals, PowerShell call-operator strings, installed-package callers, and external operator scripts still require proof.
- **False positive with proof** means the apparent singleton has an external/native/dynamic contract that was located.

No deletion is recommended from token counts alone.

## Findings

| ID | Severity | Finding | Current proof |
| --- | --- | --- | --- |
| `AUDIT-FIND-W16-001` | P2 | The live core network reader drops rerun metadata written by the desktop coordinator. | Core `ClaimResponse` loses 11 fields, core `DoneRequest` loses 12, and core `InFlightJob` loses `job_kind` and `claim_metadata`; the core worker facade loads the desktop coordinator's persisted file through that stale type. |
| `AUDIT-FIND-W16-002` | P2 | Duplicated encoder maps disagree on `h264_amf`. | A descriptor row without `family` advertises AMF but no H.264 through capability fallback, while the wizard advertises both; preset validation then rejects `video.codecFamily=h264`. |
| `AUDIT-FIND-W16-003` | P3 | Handler policy consumes a second, ungoverned Local API contract tree. | Canonical rename preview requires `preview_fingerprint`; the desktop mirror omits that obligation, and security-sensitive handler journaling reads the mirror. Only the maintenance slice has explicit dual-tree test coverage. |

### Network duplicate authority

The core and desktop network trees are not a simple obsolete/live split. Both have live inbound edges:

- coordinator/worker HTTP and persistence use `mediapipeline.desktop.network`;
- the application facade mixes core network facades with desktop lifecycle providers;
- `core.network.facade` and the rerun queue projection load `coordinator_inflight.json` through the core registry.

Several neighboring pairs remain byte-identical (`auth.py`, `library_roots.py`, `path_map.py`, `failure_reasons.py`, and `json_policy.py`), while `protocol.py`, `registry_support.py`, and persistence have diverged. This is the highest-priority consolidation family because the stale copy already performs lossy deserialization.

### Encoder policy duplication

`settings_wizard.py` and `settings_wizard_tools.py` map `h264_amf` to `h264`; `encoding_capabilities.py` does not. Existing descriptor tests always provide a valid `family`, bypassing the fallback. The immediate fix is small, but the durable repair is one encoder descriptor/name registry shared by option policy, capability facts, and wizard discovery.

### Route-contract duplication

The repository contains parallel `contracts/api_routes_*` and `desktop/api/contract_*` hierarchies. Some large pairs are still byte-identical, but the clean operations pair has already drifted. Current handler behavior for the rename-preview row is not security-divergent because its `effect` values still agree; the P3 finding is the active dual-authority gap and the observable response-contract drift, not a claim that secrets are currently logged on that route.

## Static removal candidates

### Python

An AST/token scan parsed all 770 source modules and counted references across 1,187 source/test Python files with zero parse errors. It found 52 top-level definitions whose names occur exactly once as Python `NAME` tokens. The complete path/line/symbol list is in the JSONL map.

Important caveats:

- `desktop/api/__init__.py::__getattr__` is an intentional dynamic import hook and is a known false positive.
- Public classes/functions can be package entry points even when no in-repository caller exists.
- Private helpers are stronger candidates, but still require decorator/string/dynamic lookup review.
- Ruff found zero F401, F811, or F841 issues, so this is not an unused-import/local-variable backlog.

### WebView JavaScript

Seven production identifiers have one exact JavaScript reference, at their definitions:

- `currentUiPreferenceSurface`
- `persistSharedUiPreferencesNow`
- `queueTableElement`
- `_clearPanelHolding`
- `showCompletedOutputTab`
- `noopRows`
- `settingsPatchHasCandidatePercentKeys`

The WebView uses classic scripts and public window namespaces, so HTML, Rust, native injection, and property-key contracts were checked separately. Three apparent export singletons were cleared as false positives: `MEDIA_PIPELINE_TAURI_BOOTSTRAP`, `mediaPipelinePathPicker`, and `mediaPipelinePipelineLogWindow`. All 590 public/namespace export assignments matched the canonical inventory, and its generator check passed.

### PowerShell

The parser found 2,566 function definitions across 334 PowerShell files with zero parse errors. Forty-nine definitions had no statically resolvable `CommandAst` invocation; one serialized symbol entry represents two test-local `global:Invoke-FFprobeCommand` definitions. The complete list and the 15 strongest token-singleton candidates are in the JSONL map.

These are candidates only. Dot-sourcing, call-operator strings, aliases, entrypoint loading, and external operator use are common in this codebase. Before removal, trace load order and string invocation, then run the owning stage's PowerShell checks.

### Compatibility shims

The AST classifier found 32 modules with explicit compatibility/re-export intent:

- 15 have no current production or test import;
- 11 are test-only;
- the remainder have production consumers.

The 15 zero-reference paths are primarily old desktop DTO/contract leaves. They are retirement candidates, not proven safe deletions: installed packages or external scripts may still import them. The current legacy-readiness tool does not inventory these ADR-0013 families, so package/import compatibility must be checked before removal.

## Duplication map

### Byte-identical source groups

Eleven current source pairs are byte-identical. The largest/highest-risk families are:

| Family | Examples | Risk |
| --- | --- | --- |
| API route contracts | command-file 26,943 bytes; settings-UI 14,668; network 9,886 | High maintenance risk because adjacent contract copies already differ and both trees are imported. |
| Network policy/state helpers | auth 8,981; library roots 8,865; path map 4,103; failure reasons 3,880 | High maintenance risk because protocol/registry siblings already diverged. |
| Domain-local file IO | folder-policy/schedule 1,551; queue/rename 961 | Lower risk; shared implementation must preserve domain-specific logging/error semantics. |

All paths, byte sizes, and hashes are in the machine-readable map. The command-file pair was concurrently dirty but byte-identical at the captured hash; formal findings do not rely on it.

### Python structural duplication

The normalized AST scan found 179 exact cross-file top-level definition groups and 132 same-name/same-value uppercase constant groups. Leading candidates include:

- `atomic_write_text`: eight modules, 176 duplicate lines;
- `read_json_file`: seven modules, 98 duplicate lines;
- the core/desktop network family: protocol, auth, library roots, worker state, registry support, path map, and failure reasons;
- copied failure, rerun-preview, completed-policy, route-map, Tdarr, and validation-limit constants.

Consolidation should prioritize policy, wire contracts, persisted state, and security metadata. Tiny IO helpers should move only when a common boundary preserves atomicity, encoding, logging, and failure behavior.

### PowerShell duplicate names

There are 31 duplicate production function-name groups. Policy-sensitive examples are:

- `ConvertTo-DynamicHdrInt` in probe and process code;
- audio language normalization and codec fidelity ranking in pipeline and audit code;
- queue runnable-entry selection in phase planning and worker progress;
- MP4-container policy in subtitle common and builder code;
- version/path helpers in the main engine and library-audit entrypoint;
- ten `Write-SubtitleTrackProgress` definitions/fallbacks.

Release-script helpers such as `Add-Check`, `Resolve-Tool`, and `Invoke-CapturedCommand` are more plausibly intentional standalone-script isolation. Same-name PowerShell functions can overwrite each other when dot-sourced, so load-order evidence is required even when bodies appear equivalent.

### Barrel exports

The dependency checker reported 43 `NO_BARREL_INIT_REEXPORTS` warning rows across five `__init__.py` files. Static inbound counts separate them:

- `core/kernel/contracts/__init__.py` is live: 22 production and seven test imports;
- `core/library`, `core/metrics`, and `core/repair_reconcile` barrels have no direct source/test imports;
- `core/subtitles` is test-only.

Dependency cycles are owned by the dependency audit; this worker records only the dead/duplicate re-export dimension.

## Unreachable branch result

No implementation branch was promoted as unreachable:

- Python: zero statements after unconditional terminal statements; eight `while True` loops were bounded service/poll/generator loops with internal control flow.
- JavaScript: no literal `if/while(true|false)` candidate from the bounded scan.
- Rust: Cargo reported no `dead_code` or `unused_imports` warning.
- PowerShell: zero parser errors; ten `$true` loops belonged to prompts, polling/recovery, subtitle conversion, acceptance, or audit tooling.

This does not prove data-dependent branches are reachable. Platform-specific, reflection-based, and impossible-state branches require semantic/runtime proof.

## Historical reconciliation

Previously named Python candidates such as `_line_references_target`, `collect_inbound_references`, `make_auth_header`, `QueuePriorityItemPayload`, `NetworkLifecycleCommandPayload`, `list_high_paths`, and `list_hold_paths` are now removed/resolved. `Resolve-DynamicHdrPolicy` is live. Several prior WebView and PowerShell candidates remain in the current static lists.

The legacy-removal readiness check found no old config-schema file, flat command-payload file, flat facade/service, root launcher, Pipeline-root launcher, or `Pipeline/Modules` implementation. Residual broad term matches were current helper names, generated indexes, explicit negative rules, inventories, or historical prose—not resurrected implementation.

## Validation

Passed:

- Targeted Python suite: **125 tests and 490 subtests passed** in 40.24 seconds across network protocol/rerun, API command/handler policy, and preset capability contracts.
- Ruff F401/F811/F841 scan across `src/mediapipeline`: **passed**.
- Cargo check `--all-targets`: **passed**.
- Cargo Clippy with `-W dead_code -W unused_imports`: **passed with no scoped warning**; two unrelated `std::io::Error::other` style suggestions were recorded in the error ledger.
- WebView inventory generator `--check`: **passed**.
- Dependency checker report-only run: **completed**; barrel warnings were classified in the map.
- Legacy-removal readiness report-only run: **completed** with zero legacy implementation files.
- Final JSONL parse and repository finding/error schema checks: **passed**.

No real-media validation was run or required because this worker made no source changes. Any future consolidation touching network state, media policy, PowerShell stage behavior, or source/output movement must use the validation rung specified in the associated finding and the no-touch boundary register.
