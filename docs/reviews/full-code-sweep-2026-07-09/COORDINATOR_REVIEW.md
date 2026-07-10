# Full Code Sweep — Coordinator Review

## Metadata

| Field | Value |
|---|---|
| Review date | 2026-07-09 |
| Collection status | Complete |
| Expected worker reports | 15 |
| Usable worker reports | 15/15 |
| Missing or unusable reports | None |
| Change packet | MP-CHANGE-2026-0709-002 |
| Production changes made | None |

`git status --short` before collection showed extensive pre-existing dirty and untracked work across WebView, backend, PowerShell, tests, inventories, generated context, and unrelated change packets. It is not attributed to this review. Only this Markdown file and the named documentation packet were changed by the coordinator.

## Worker report collection manifest

| Tab | Expected file | Exists | Usable | Findings by severity | Notes |
|---|---|---:|---:|---|---|
| Home | `home-review.md` | Yes | Yes | 0/2/1/0 | 21,270 bytes; trace, evidence, no-finding, tests, handoff, limits present. |
| Launch | `launch-review.md` | Yes | Yes | 0/1/1/0 | 15,926 bytes; complete report structure. |
| Telemetry | `telemetry-review.md` | Yes | Yes | 0/3/1/0 | 14,720 bytes; complete report structure. |
| Metrics | `metrics-review.md` | Yes | Yes | 0/3/3/1 | 20,057 bytes; complete report structure. |
| Queue | `queue-review.md` | Yes | Yes | 1/1/2/1 | 14,949 bytes; evidence gives files plus line ranges. |
| Completed Output | `completed-output-review.md` | Yes | Yes | 0/1/1/1 | 17,968 bytes; complete report structure. |
| Pending Publish | `pending-publish-review.md` | Yes | Yes | 0/0/2/1 | 14,884 bytes; complete report structure. |
| Rename | `rename-review.md` | Yes | Yes | 0/2/2/1 | 23,152 bytes; stated P0 is none. |
| Reports | `reports-review.md` | Yes | Yes | 0/3/1/1 | 13,891 bytes; stated P0 is none. |
| Network Workers | `network-workers-review.md` | Yes | Yes | 0/1/2/1 | 15,094 bytes; stated P0 is none. |
| Libraries | `libraries-review.md` | Yes | Yes | 0/2/1/1 | 18,287 bytes; complete report structure. |
| Schedule | `schedule-review.md` | Yes | Yes | 0/0/1/0 | 19,172 bytes; stated P0/P1/P3 are none. |
| Settings | `settings-review.md` | Yes | Yes | 0/3/1/0 | 21,211 bytes; complete report structure. |
| Diagnostics | `diagnostics-review.md` | Yes | Yes | 0/1/2/1 | 16,611 bytes; complete report structure. |
| Maintenance | `maintenance-review.md` | Yes | Yes | 0/0/2/0 | 16,574 bytes; complete report structure. |

All expected files were read in full. “Findings by severity” is P0/P1/P2/P3 after coordinator review of each report; headings that explicitly state “none” are not counted as findings.

## Executive assessment

Overall risk is **high until the rerun integrity blocker is repaired**. One verified P0 and seven verified P1 root-cause findings remain after merging repeated symptoms. The major systemic themes are fail-open/stale state representation, inconsistent strict backend command intent, mutation transaction/journal ordering, and contract/authority drift. Immediate operator restriction: do not accept or run Queue CSV rerun from this tree; do not rely on degraded/stale dashboard evidence as current close/active-work proof. Collection is complete; runtime behavior remains unproven.

## Verified finding ledger

| Coordinator ID | Severity | Originating worker finding(s) | Affected tab(s) | Confidence | Exact evidence | Impact | Smallest safe remediation | Required validation |
|---|---|---|---|---|---|---|---|---|
| COORD-001 | P0 | QUEUE-001, QUEUE-004 | Queue, Launch | High | `src/mediapipeline/core/processes/rerun_policy.py` is 25,032 NUL bytes; `py_compile` returns null-byte `SyntaxError`; matching generated summary is NUL-only. | Rerun safeguards cannot import. | Restore source, inspect NUL artifacts, regenerate context. | Rerun API/WebView/PowerShell tests; real-media rerun. |
| COORD-002 | P1 | QUEUE-002 | Queue | High | `core/queue/file_overrides.py:199-213`; `ops/pipeline/engine/queue/file_overrides.ps1:174-225` both return empty manifest on malformed input. | Persisted media-routing intent silently vanishes. | Typed parse health and backend fail-closed result. | Python/PS parity negative tests. |
| COORD-003 | P1 | HOME-001, DIAGNOSTICS-001, TELEMETRY-002/003, REPORTS-001/002, METRICS-003 | Home, Diagnostics, Telemetry, Reports, Metrics | High | `app.js:961-976,1078-1103` retains `lastCloseReadiness`; cited status/progress/report readers collapse error/terminal evidence into current-looking output. | Unknown state can look safe, idle, empty, or current. | Shared unavailable/stale DTO and UI policy; historical cache never drives controls. | safe→failure→recovery browser/API fixtures. |
| COORD-004 | P1 | HOME-002, LAUNCH-001 | Home, Launch | High | Pipeline control accepts `kill` without strict confirmation; `PipelineStartCommandPayload` permits absent `mode`, normalized to `once`. | Direct authenticated call can bypass intended confirmation or unspecified launch intent. | Strict backend boolean for kill and required typed mode. | Contract/HTTP no-service-call tests and browser smoke. |
| COORD-005 | P1 | COMPLETED-001, NETWORK-001, SETTINGS-003, RENAME-002 | Completed, Network, Settings, Rename | Medium-high | Repair write precedes non-strict journal; token rotates before join-blob validation; settings save lacks CAS; undo path restoration lacks operation-root proof. | Mutable state can lack durable audit/rollback or overwrite/escape scope. | Preflight, bind version/root/fingerprint, strict journal before commit or compensate. | Forced persistence and concurrent/path-boundary tests. |
| COORD-006 | P1 | LIBRARIES-001/002, RENAME-001 | Libraries, Rename | Medium-high | Profile-derived roots/promotion rules can outlive profile changes; TV destination lacks final configured-root validation. | Effective path/promotion policy can diverge from operator configuration. | Validate final resolved path; atomically reconcile generated promotion rules. | Profile lifecycle and derived-destination boundary tests. |
| COORD-007 | P1 | METRICS-001/002, REPORTS-003 | Metrics, Reports | Medium | Sidecar cache and partial backfill may be treated as complete history; failure cap hides blockers. | Operator evidence overclaims coverage. | Publish authority/completeness/blocker summary independently of visible rows. | partial/corrupt/>100-row fixtures. |
| COORD-008 | P2 | QUEUE-003, NETWORK-002/004 | Queue, Network | High | Priority payload/JS use `position`, but `api_routes_command.py` and inventories omit it; confirmed network result returns dry-run-like effect. | Public command contracts misdescribe real mutation. | Canonical contract update plus response-contract tests. | Contract/inventory/result tests. |
| COORD-009 | P2 | PENDING-001/002, HOME-003, COMPLETED-002, SETTINGS-004, RENAME-003 | Pending, Home, Completed, Settings, Rename | Medium | UI drain verdict blocks backend evaluation; index refresh invokes recovery; truthy close values; parse health/preview/fingerprint gaps. | Ownership and degraded-evidence ambiguity. | Backend preflight and server-issued fingerprint/parse-health evidence. | Targeted API/browser/PS tests; real-media only if publish/drain changes. |

## Detailed verified findings

### CSW-2026-07-09-COORD-001 — [P0] Rerun-policy source integrity failure

- Originating worker report(s): Queue.
- Verification status: verified by byte inspection and Python compilation.
- Exact evidence: `rerun_policy.py` and its generated summary are NUL-only; `HEAD` has normal Python source.
- Root cause: active-worktree integrity failure, not a Queue presentation defect.
- Affected workflow: Queue CSV rerun → rerun facade/preview/results → pipeline launch.
- Impact: release-critical rerun validation and safeguards cannot execute.
- Why severity is appropriate: an active source module for a high-risk media workflow cannot import.
- Smallest safe remediation: restore intended content without overwriting unrelated dirty work, then regenerate summaries.
- Safety/architecture constraints: preserve source/scratch isolation and backend-owned launch/deduplication; no frontend workaround.
- Required validation: rerun policy/preview/results/API/WebView/PowerShell checks plus representative real-media rerun.
- Related or duplicate worker findings: QUEUE-004 merged here.

### CSW-2026-07-09-COORD-002 — [P1] Persisted override corruption fails open

- Originating worker report(s): Queue.
- Verification status: verified in Python and PowerShell consumers.
- Exact evidence: both cited readers return the versioned empty manifest on malformed existing content.
- Root cause: absence and parse failure share one value.
- Affected workflow: Queue override display/save and PowerShell route/audio/subtitle processing.
- Impact: a corrupt manifest can act as deliberate absence.
- Why severity is appropriate: it bypasses policy intent in a media workflow, though it does not itself mutate source media.
- Smallest safe remediation: typed backend parse-health result with safe processing block/review state.
- Safety/architecture constraints: UI renders backend result only; do not add frontend validation authority.
- Required validation: malformed manifest parity tests and rerun/pipeline policy checks.
- Related or duplicate worker findings: none.

### CSW-2026-07-09-COORD-003 through COORD-009

The ledger is the detailed evidence record for these merged findings. They were not multiplied by tab count: COORD-003 is one degraded-state root cause, COORD-004 one command-intent root cause, COORD-005 one transaction-boundary family, COORD-006 one resolved-path/profile-authority family, COORD-007 one evidence-completeness family, and COORD-008/009 bounded contract/ownership P2s.

## Systemic cross-tab findings

Frontend/backend ownership is generally sound, but Pending Publish drain gating is a concrete UI-authority exception. Strict booleans and fresh fingerprints exist in repair/queue flows but not uniformly in force-stop/start/rename/settings. JSON remains authoritative; SQLite/generated/cache evidence must never be presented as complete state without provenance. Route/schema/inventory drift exists for Queue position and Network effects. Filters, selected rows, and render caps were consistently documented as presentation-only; Reports/Metrics need a backend blocker/completeness summary so that claim remains meaningful. Source/scratch/output and pending-publish protections remain backend/PowerShell owned; no review justified moving them into WebView. Existing tests are strongest on normal rendering, weaker on persistence failure, stale transition, concurrency, truncation, and recovery.

## Rejected, merged, or needs-confirmation findings

| Worker finding | Disposition | Reason | Evidence still needed |
|---|---|---|---|
| QUEUE-004 | Merged | Generated NUL summary is same integrity incident as COORD-001. | Restoration scan results. |
| HOME-003 | Merged P2 | Boolean coercion is one facet of COORD-003. | Shared response-schema test. |
| COMPLETED-003, NETWORK-004, Libraries/Reports/Schedule P3s | Lower severity | Wording/inventory/observability defects do not bypass current backend guards. | Focused assertions after higher-priority fixes. |
| PENDING-003 | Needs confirmation | No production proposal producer was found, but intent may be deliberately dry-run-only. | Product/contract decision and production-source trace. |
| Maintenance P2s | Needs confirmation | Static evidence supports contract mismatch; release/runtime reproduction was not run. | Focused builder/dry-run tests. |

## Remediation sequence

1. **Containment:** Queue/process owner blocks CSV rerun acceptance (COORD-001). No-touch: source/scratch/output and process lifecycle. Rung: targeted + real-media rerun.
2. **P0/P1 fixes:** Queue override, status/telemetry, Launch/Home, Completed/Network/Settings/Rename, Libraries owners address COORD-002–007. No-touch: command journal, confirmation, publish/drain, rename and network lifecycle. Rung: targeted API/WebView/PowerShell; real media only for rerun/publish/drain/media movement.
3. **Shared contracts:** desktop/contracts/inventory owners correct COORD-008 and schema response evidence. Rung: contract/inventory/API tests.
4. **P2 functional work:** Pending/Completed/Settings/Rename owners resolve COORD-009. Rung: targeted tests; Pending index/drain change requires real-media deferred-publish/drain validation.
5. **P3:** maintainers improve guidance, inventories, and assertions after behavior is fixed.

## Validation plan

Run focused Python contract/facade tests for strict payloads, journaling, settings CAS, rename roots, profile lifecycle, and state readers; Local API smoke for lifecycle/command results; affected WebView browser smokes for unavailable state and no-mutation boundaries; focused PowerShell queue/pending-publish/rerun checks; release self-test after code changes. Real-media validation is mandatory for rerun, FFmpeg/media policy, subtitle/audio, publish/drain, or source/scratch/output movement. None of these tests proves playback or real media unless explicitly exercising it.

## Coverage and limits

Collected reports: all fifteen listed in the collection manifest. No report is missing or unusable. No live API/browser/pipeline/media operation was invoked; runtime behavior, UNC timing, crash recovery, and playback remain unverified. The dirty worktree was preserved; its unrelated changes are neither validated nor attributed here.

## Change-packet closeout

All 15 report files plus this coordinator review are covered by `MP-CHANGE-2026-0709-002`. `git diff --check` passed and the packet JSON parses. Strict change-packet validation did not pass because unrelated `MP-CHANGE-2026-0707-001.json` is malformed and uncovered; the docs release self-test exceeded the available 60-second execution window.
