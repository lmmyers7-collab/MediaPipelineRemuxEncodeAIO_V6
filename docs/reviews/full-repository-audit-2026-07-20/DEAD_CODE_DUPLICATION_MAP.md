# Dead Code and Duplication Map

Status: current cross-language static scan complete; removal candidates remain non-authoritative until their dynamic/external contracts are proved.

This map consolidates the exhaustive worker evidence in
`workers/worker-16-dead-code-duplication-map.md` and its 15-row JSONL map. The
captured snapshot covered 2,085 first-party files under `src/`, `tests/`,
`ops/`, and `apps/` (38,248,956 bytes; snapshot SHA-256
`5a688bf53375c2dbe9b520001bc0b977fbd8275c2fc5264b2208c11ae6c0a421`).
Bundled runtime, Cargo target output, `node_modules`, and caches were excluded
from semantic dead-code inference and remain covered by their dedicated
runtime/vendor inventory partition.

## Confirmed current defects

| ID | Severity | Root cause | Consequence |
| --- | --- | --- | --- |
| `AUDIT-FIND-W16-001` | P2 | The live core network reader is a lossy duplicate of the desktop coordinator protocol. | `ClaimResponse` loses 11 fields, `DoneRequest` loses 12, and `InFlightJob` loses `job_kind`/`claim_metadata` while reading the coordinator's persisted state. |
| `AUDIT-FIND-W16-002` | P2 | Duplicated encoder-family maps disagree on `h264_amf`. | Descriptor fallback advertises no H.264 family while the wizard does; preset validation can reject `video.codecFamily=h264`. |
| `AUDIT-FIND-W16-003` | P3 | Handler policy consumes a second, ungoverned Local API contract tree. | The desktop rename-preview mirror omits canonical `preview_fingerprint`; adjacent copies already drift even where current security effects still agree. |

These are duplication defects, not blanket permission to merge files. Network
state, request contracts, and encoder policy need one authority with migration
tests; small IO helpers may legitimately retain domain-specific logging and
failure semantics.

## Static removal candidates

- Python: 770 source modules parsed with zero errors. Fifty-two top-level
  definitions occur exactly once as a Python `NAME` token. Dynamic imports,
  decorators, package entry points, and external consumers prevent automatic
  deletion. Ruff found no scoped F401/F811/F841 issue.
- WebView: seven production identifiers occur only at their definitions:
  `currentUiPreferenceSurface`, `persistSharedUiPreferencesNow`,
  `queueTableElement`, `_clearPanelHolding`, `showCompletedOutputTab`,
  `noopRows`, and `settingsPatchHasCandidatePercentKeys`. Classic-script
  globals and native injection still require runtime/public-contract proof.
- PowerShell: 2,566 functions across 334 files parsed without error. Forty-nine
  definitions lack a statically resolvable `CommandAst` invocation; the 15
  strongest token-singleton candidates are retained in the worker JSONL.
  Dot-sourcing, call-operator strings, aliases, and operator scripts make these
  candidates only.
- Compatibility shims: 32 explicit re-export/compatibility modules were found;
  15 have no current source/test import and 11 are test-only. Installed-package
  compatibility must be checked before retirement.

Three apparent WebView export singletons were disproved:
`MEDIA_PIPELINE_TAURI_BOOTSTRAP`, `mediaPipelinePathPicker`, and
`mediaPipelinePipelineLogWindow`. All 590 public/namespace assignments match
the canonical inventory.

## Duplication inventory

| Dimension | Current result | Priority interpretation |
| --- | ---: | --- |
| Byte-identical source groups | 11 pairs | API contract and core/desktop network pairs are high-maintenance risk; domain IO pairs are lower risk. |
| Exact cross-file normalized Python definition groups | 179 | Consolidate policy/wire/state/security duplication before generic helpers. |
| Same-name/same-value uppercase Python constant groups | 132 | Review copied policy and validation limits first. |
| Duplicate production PowerShell function-name groups | 31 | Prove dot-source load order because later definitions can overwrite earlier ones. |
| Dependency `NO_BARREL_INIT_REEXPORTS` warnings | 43 rows across 5 `__init__.py` files | `core/kernel/contracts` is live; three barrels have no direct source/test imports; `core/subtitles` is test-only. |

Leading Python structural families include eight `atomic_write_text`
implementations (176 duplicate lines), seven `read_json_file`
implementations (98 lines), duplicated core/desktop network protocol and state
helpers, and copied failure/rerun/completed-policy/route-map/Tdarr constants.

Policy-sensitive PowerShell duplicates include dynamic-HDR conversion, audio
language normalization, codec fidelity ranking, runnable-queue selection,
MP4-container policy, version/path helpers, and ten
`Write-SubtitleTrackProgress` definitions or fallbacks. Standalone release
helpers are more plausibly intentional isolation, but still need load-order
evidence.

## Reachability conclusion

No implementation branch was proved unreachable. The bounded scans found no
Python statement after an unconditional terminator, no literal JavaScript
`if/while(true|false)` candidate, no scoped Rust dead-code/unused-import
warning, and no PowerShell loop that survived semantic classification as
unreachable. This does not prove data-dependent, platform-specific,
reflection-based, or impossible-state branches are reachable.

## Historical reconciliation and validation

Previously named candidates `_line_references_target`,
`collect_inbound_references`, `make_auth_header`, `QueuePriorityItemPayload`,
`NetworkLifecycleCommandPayload`, `list_high_paths`, and `list_hold_paths` are
removed/resolved; `Resolve-DynamicHdrPolicy` is live. No prohibited legacy
config-schema, flat command/facade/service, root launcher, Pipeline-root
launcher, or `Pipeline/Modules` implementation was found.

Completed W03 review also proves that the retained legacy queue-priority
compatibility helpers are not harmless dead code: `AUDIT-FIND-W03-003` traces
their callable rename/retimestamp behavior against source media without a named
safety policy. They must be removed or fenced through the source-immutability
authority after caller/compatibility proof; their apparent legacy status is not
permission to ignore the mutation path.

Completed W05 review finds live semantic duplication across Python planning and
PowerShell execution rather than unreachable code. `W05-003`, `W05-004`, and
`W05-010` show that no-audio, preferred-subtitle conversion, and video-stream
selection are encoded differently on the two sides of the boundary. The repair
is a single tested policy contract or generated parity evidence, not deletion
based only on reference counts.

Validation passed: 125 targeted tests plus 490 subtests, Ruff unused/import
checks, Cargo `--all-targets`, scoped Clippy dead-code/unused-import checks,
WebView inventory generation, dependency report-only analysis, legacy-removal
readiness, and finding/error JSONL schema validation. No real-media validation
was required because this map changed no application behavior.
