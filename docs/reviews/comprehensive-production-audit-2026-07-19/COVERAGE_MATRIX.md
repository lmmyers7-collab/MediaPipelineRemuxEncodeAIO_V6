# Coverage Matrix

Campaign: `comprehensive-production-audit-2026-07-19`  
Status vocabulary: `not_started`, `in_progress`, `complete`, `deferred`, `blocked`  
Result vocabulary: `finding`, `no_finding_with_limits`, `requires_more_evidence`, `not_applicable`

No-finding results are bounded conclusions. Each completed row must identify
the evidence checked and what it cannot prove.

## Foundations and Provenance

| ID | Coverage unit | Status | Result | Evidence / limitation |
| --- | --- | --- | --- | --- |
| BAS-01 | Date, environment, host, OS, and local tool versions | complete | no_finding_with_limits | `evidence/BASELINE.md`; .NET SDK unavailable |
| BAS-02 | Branch, exact HEAD, upstream, and recent history | complete | no_finding_with_limits | Local refs only; no fetch |
| BAS-03 | Dirty status, tracked/untracked/staged split, and diff statistics | complete | no_finding_with_limits | Initial and concurrent snapshots recorded; initial raw status hashed/summarized but not stored |
| BAS-04 | HEAD vs. overlay vs. behavioral delta | in_progress | requires_more_evidence | Delta needs subsystem tests against a stable snapshot |
| BAS-05 | Known validation baseline and high-risk gates | complete | requires_more_evidence | Canonical claims are historical until independently rerun |
| HIST-01 | 2026-07-09 full code sweep | complete | finding | Eight still-present carry-forwards are now verified: three P1 settings defects, four P2 workflow/UX defects, and one P3 Pending Publish operability defect; other candidates require verification |
| HIST-02 | 2026-07-13 full functional audit | complete | requires_more_evidence | Fixed findings plus retained blocked/skipped and runtime gaps |
| HIST-03 | 2026-06-11 function/module audit | complete | requires_more_evidence | Every ID classified; ten closure-evidence gaps; FR-015 real-media gap |
| HIST-04 | 2026-06-15 Network audit | complete | no_finding_with_limits | All 35 historically fixed/covered; present-source sampling pending |
| HIST-05 | 2026-07-12 CodeQL audit | complete | requires_more_evidence | Authoritative remote closure outstanding |
| HIST-06 | Canonical-status contradictions | in_progress | requires_more_evidence | Inventory/authority drift candidates require source verification |

## Cross-Layer Ownership

| ID | Coverage unit | Status | Result / limitation |
| --- | --- | --- | --- |
| OWN-01 | Tauri window/backend lifecycle and OS dialogs, not media policy | not_started | — |
| OWN-02 | WebView rendering/intent staging without direct mutation | complete — bounded browser evidence | Current 977-row authored ledger; all 34 browser modules/42 tests passed with zero suite skips; 42 no-mutation/ownership tests passed; 41 native controls remain recipe-gated and 28 mutation controls remain intentionally excluded |
| OWN-03 | Local API auth, routes, strict payloads, and effect class | not_started | — |
| OWN-04 | Application facade/DTO orchestration boundary | not_started | — |
| OWN-05 | Python policy/state ownership without transport leakage | in_progress | Finding: `CSW-2026-07-09-SETTINGS-001`; broader ownership review pending |
| OWN-06 | PowerShell production media/tool execution | not_started | — |
| OWN-07 | Helper arguments, timeouts, exits, and result handling | not_started | — |
| OWN-08 | JSON/JSONL/manifest authority over SQLite/support logs | in_progress | Findings: `SETTINGS-002` and `SETTINGS-003`; broader authority/mirror review pending |
| OWN-09 | Confirmation, auth, journal, and duplicate guards | not_started | — |
| OWN-10 | Generated dependency/navigation integrity | in_progress | 569 files remain unknown/unparsed; maps are navigation, not proof |

## Vertical Workflows

| ID | Workflow | Required vertical trace | Success and failure evidence | Status | Result | Evidence / limitation |
| --- | --- | --- | --- | --- | --- | --- |
| WF-01 | Startup, bootstrap, runtime discovery, single instance, shutdown | Tauri → bootstrap token/API → backend lifecycle → child processes → close evidence | Clean start; missing runtime/config; duplicate instance; backend crash/restart; safe close | in_progress | finding | `CPA-2026-07-19-004`, `006`, and `CSW-2026-07-09-HOME-003`; native crash/wait-error and remaining bootstrap failure paths pending |
| WF-02 | Close-readiness and process lifecycle | UI controls → strict command routes → journal/duplicate guard → pause/stop/force-stop → terminal state | No work; active work; duplicate/concurrent request; timeout/crash; restart/forced shutdown | in_progress | finding | `CPA-2026-07-19-005`, `006`, `HOME-003`, and `TELEMETRY-004`; broader stop/duplicate/native descendant evidence pending |
| WF-03 | Queue discovery and launch | Queue UI → filters/selection/overrides/order/strategy/rerun → route/contract → queue/process services → engine plan | Empty/malformed/stale queue; duplicate/concurrent launch; partial write; retry/recovery | in_progress | requires_more_evidence | Historical `QUEUE-001`–`004` now source/test verified fixed on current tree; broad overlay launch/engine trace and duplicate/recovery paths pending |
| WF-04 | Settings and profiles | Builder/preview → strict save/promote contract → config services → PSD1/runtime overlay evidence | Missing/partial/invalid state; inheritance/conflict; concurrent save; reload/restart | in_progress | finding | `CSW-2026-07-09-SETTINGS-001`, `002`, `003`, and `CPA-2026-07-19-008`; token boundary, runtime extras, and cross-process race independently verified; inheritance and packaged reload pending |
| WF-05 | Probe and remux/encode routing | Source facts → probe contracts → decide policy → FFmpeg/MKVToolNix args → verification | Probe failure; fallback; size guard; tool timeout/crash; partial output; restart | in_progress | finding | `CPA-2026-07-19-002`; broader media-policy and real-media evidence pending |
| WF-06 | Subtitles | UI/config → language/preservation contracts → ASS/TX3G/PGS/VobSub helpers → sidecars/review | Missing/malformed streams; OCR/conversion failure; preservation proof; recovery | in_progress | finding | `CPA-2026-07-19-007`; targeted policy tests passed historically/current-agent evidence, representative media and preservation proof pending |
| WF-07 | Audio | Profile/config → stream selection/defaults → passthrough/transcode/downmix → output verification | Missing language/default; channel edge cases; tool failure; retry/fallback | not_started | — | — |
| WF-08 | Source, scratch, partial, final, cleanup, path boundaries | Path inputs → normalization/guards → scratch copy → partial/final cleanup → evidence | Traversal/collision; permission denial; disk exhaustion; partial copy/write; cancellation | in_progress | finding | `CPA-2026-07-19-003`; P1 independently verified; broader path/cleanup review pending |
| WF-09 | Publish and pending publish | Completion → publish policy → park manifest/transaction → drain/retry → final placement and sidecars | Unsafe destination; partial move; duplicate drain; crash/restart; evidence consistency | in_progress | finding | `CSW-2026-07-09-PENDING-003`; historical 001/002 verified fixed and focused ownership/safety/browser tests pass; real-media deferred publish/drain remains gated |
| WF-10 | Rename preview/apply/undo | UI preview → fingerprint-bound strict apply → collision/boundary guards → undo/sidecars | Stale preview; changed source; collision; partial apply; restart/rollback | in_progress | finding | `CSW-2026-07-09-RENAME-004`; historical 001/002/003/005 verified fixed, 57 focused tests pass; packaged refresh/restart and representative filesystem interruption remain pending |
| WF-11 | Network coordinator/worker | Network UI → auth/join/claim/done/release contracts → provider hooks → recovery | Invalid auth/input; duplicate claim; interruption; stale lease; restart; lifecycle boundaries | not_started | — | — |
| WF-12 | Diagnostics, telemetry, reports, metrics, logs | UI freshness/authority → read routes → state/log sources → redaction → recovery evidence | Empty/malformed/stale/partial/denied state; source-count conflicts; restart | in_progress | finding | `CSW-2026-07-09-HOME-003`, `TELEMETRY-004`, and maintenance finding; reports/metrics/log redaction review pending |
| WF-13 | Scheduling and watch folders | UI/config → schedule/watch contracts → trigger → launch guard → restart/missed-trigger evidence | Collision; duplicate trigger; downtime/restart; malformed state; cancellation | not_started | — | — |
| WF-14 | Release packaging and rollback | Build/test scripts → manifest/exclusions → packaged runtime/tools/config → install/launch/close/rollback | Missing dependency; personal config leak; corrupt artifact; clean-install/rollback failure | not_started | — | — |

## Independent Review Passes

| ID | Pass | Required questions | Status | Result | Evidence / limitation |
| --- | --- | --- | --- | --- | --- |
| PASS-01 | Architecture and ownership | Are mutation, policy, persistence, and evidence owned by the correct layer? | not_started | — | — |
| PASS-02 | Correctness and contract consistency | Do route, schema, DTO, service, engine, and UI expectations agree? | in_progress | finding | Settings inventories and runtime-extra authority contradict source/runtime behavior; broader pass pending |
| PASS-03 | Failure handling and recovery | Are failures visible, terminal states trustworthy, and retries/restarts safe? | in_progress | finding | Rename completed-undo state is overwritten by apply-only history; lifecycle and pending recovery evidence also active; broader pass pending |
| PASS-04 | Security and untrusted input | Are secrets, auth, paths, process invocation, logs, and client boundaries safe? | in_progress | finding | `SETTINGS-001` and `002`; broader auth/path/process/log review pending |
| PASS-05 | Data integrity and rollback | Are writes atomic, idempotent, provenance-bound, and recoverable? | in_progress | finding | `SETTINGS-003` lost-update reproduction plus scratch/lifecycle findings; broader pass pending |
| PASS-06 | Concurrency and stale state | Are races, duplicates, stale previews/claims, and restarts handled? | in_progress | finding | `SETTINGS-003`, `CPA-2026-07-19-004`, schedule restart, and `RENAME-004` stale-history state; broader pass pending |
| PASS-07 | Test quality | Do tests assert behavior rather than structure; what contracts are falsely green or absent? | in_progress | finding | `CPA-2026-07-19-001` remediated in the current overlay with direct-only/numeric drift enforcement; `007`, `008`, and the missing rename apply→undo→refresh sequence remain; broader pass pending |
| PASS-08 | Runtime and integration consistency | Do installed runtimes, helpers, launchers, contracts, and cross-language paths agree? | in_progress | finding | `SETTINGS-001`, `002`, and Tauri/media helper findings; broader pass pending |
| PASS-09 | Operator failure-state UX | Are loading, empty, stale, malformed, partial, denied, and failed states actionable? | in_progress | finding | Pending orphan dead-end, stale completed-undo presentation, and lifecycle/telemetry findings; broader pass pending |
| PASS-10 | Release and production readiness | Can the documented package start, operate, close, recover, and roll back safely? | not_started | — | — |
| PASS-11 | Adversarial disproof | What evidence could falsify important no-finding conclusions, and was it attempted safely? | not_started | — | — |

## Cross-Cutting Failure Matrix

Each material workflow must disposition the applicable modes below; workflow
rows may link to targeted subrows as the review expands.

| Failure mode | Applicable workflows | Status | Evidence / disposition |
| --- | --- | --- | --- |
| Empty or missing state | WF-01–WF-14 as applicable | not_started | — |
| Malformed or partially valid state | WF-01–WF-14 as applicable | not_started | — |
| Stale or conflicting state | WF-01–WF-04, WF-09–WF-13 | in_progress | `SETTINGS-003` proves cross-process stale-authority lost update; `RENAME-004` proves completed undo becomes stale after history refresh; remaining workflows pending |
| Duplicate or concurrent submission | WF-02–WF-04, WF-09–WF-13 | in_progress | `SETTINGS-003` plus duplicate-backend path; remaining workflows pending |
| Backend restart | WF-01–WF-04, WF-09–WF-13 | not_started | — |
| Child-process crash or timeout | WF-01, WF-02, WF-05–WF-07, WF-11, WF-14 | not_started | — |
| Partial filesystem write | WF-03–WF-10, WF-12–WF-14 | not_started | — |
| Permission denial | WF-01, WF-03–WF-14 | not_started | — |
| Disk exhaustion (safe simulation only) | WF-05–WF-10, WF-12, WF-14 | not_started | — |
| Network interruption | WF-11 and dependency checks | not_started | — |
| Cancellation or forced shutdown | WF-01–WF-03, WF-05–WF-11, WF-13 | not_started | — |
| Retry and recovery evidence consistency | WF-01–WF-14 as applicable | not_started | — |

## Campaign Gates

| Gate | Condition | Status | Evidence |
| --- | --- | --- | --- |
| G-01 | HEAD and working-tree overlay documented | complete | `evidence/BASELINE.md` |
| G-02 | Historical finding reconciliation complete | complete | `DISPOSITION_LEDGER.md` |
| G-03 | P0/P1 independent verification complete | in_progress | `CPA-2026-07-19-003`, `004`, `005` and historical `SETTINGS-001`, `002`, `003` independently verified; future P0/P1 findings must also satisfy gate |
| G-04 | Representative real-media evidence either complete or explicitly missing | not_started | — |
| G-05 | Change packet has exact campaign touched-path coverage | in_progress | `MP-CHANGE-2026-0719-002` |
| G-06 | Generated summaries/inventories current for campaign changes | not_started | — |
| G-07 | Every row complete, deferred, or blocked with concrete reason | not_started | — |

## Inventory and Authority Drift Candidates

These observations require source/generator verification and are not findings
merely because documents disagree.

| ID | Observation | Required proof | Status |
| --- | --- | --- | --- |
| INV-01 | HEAD has 25 browser wrappers/33 modules and overlay 25/34; active docs reported 24/26 or 24/27 and the canonical map check was false-green | `CPA-2026-07-19-001`; v2 `SMOKE_WRAPPER_MAP.json`; targeted generator tests and `--check` | complete — remediated in current overlay; 45 monitored claims across 12 active docs reconcile 37 total wrappers, 25 browser wrappers, 34 browser modules, and 9 direct-only modules |
| INV-02 | Settings matrices disagree by one metadata key, binding, and unique binding | `CPA-2026-07-19-008` | complete — finding |
| INV-03 | API inventory total says 117 POST while its heading says 116 and cites a missing test filename | Regenerate/check against route contracts | not_started |
| INV-04 | Pending fixture inventory uses stale `app/publish/` paths | Compare active source/tests and generator | not_started |
| INV-05 | Historical 970-control browser result versus current DOM/evidence/catalog population | `WEBVIEW_TOUCHPOINT_LEDGER.json`; row-derived audit summary; all-browser and no-mutation validation | complete — current authored denominator is 977 with 816 passed, 92 legitimately blocked, 41 manual/native-only, 28 intentionally excluded, and zero failing/stale/unexplained rows |
| INV-05 | No-touch register calls Network lifecycle outside WebView/read-only while promoted guarded lifecycle routes have frontend callers | Verify current callers, route effects, guards, and intended boundary | not_started |
| INV-06 | Module map says JSON settings authority with PSD1 projection; runtime/log inventories still call PSD1 live authority | Trace runtime load/merge/projection and tests | not_started |
| INV-07 | Pending manifests are described as per-job directories, `*.manifest.json`, and `{transaction_id}.json` | Trace schemas, writers, readers, and distinct artifact types | not_started |
| INV-08 | Generated project/dependency maps classify 569 files unknown/unparsed | Run generator checks and sample classification behavior | not_started |
| INV-09 | Test inventory names a non-existent Metrics degraded-state filename | Compare disk, generated smoke map, and inventory source | not_started |
