# Audit Master Registry - 2026-06-17

Change packet: `MP-CHANGE-2026-0618-001`

This bounded synthesis resolves the follow-up issues raised by
`Docs/ai-audits/2026-06-17-audit-coordinator.md`. It does not replace
`AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, or `docs/OPEN_WORK_CHECKLIST.md`,
and it is not an implementation plan. It is a merge aid for the 2026-06-17
audit set.

## Executive Summary

All expected audit reports now exist after adding
`Docs/ai-audits/2026-06-17-test-coverage-gap-analysis.md`. Existing worker
reports were not rewritten. Instead, this registry maps their local headings and
IDs to the coordinator ID scheme, groups duplicate findings by root cause,
records prompt issue disposition, answers the coordinator open questions, and
sets a validation-first remediation order.

The top consolidated risks are:

1. Release trust and worktree/change-packet hygiene.
2. Source/scratch/output data-safety risks, especially stale partial cleanup
   and single-file source-root enforcement.
3. Network coordinator split-brain, ownership, durable done, and path identity.
4. Pending-publish drain concurrency and final-placement proof.
5. Command journal durability and exception evidence.
6. Media-policy parity across Python preview/planner and PowerShell runtime.
7. Tauri/WebView safety-validation fail-closed behavior.
8. Configuration drift across templates, profiles, schemas, backend metadata,
   WebView staging, and LocalBase overlays.
9. Startup/shutdown, long-run memory/resource, UI double-submit, and operator
   journey risks that can make safe behavior hard to verify.
10. Future-feature blockers around durable shared state, remote auth/RBAC,
    mutation ownership, and provider abstractions.

## Report Inventory

| Track | Expected file | Status |
|---|---|---|
| Coordinator | `Docs/ai-audits/2026-06-17-audit-coordinator.md` | Present |
| ARCH | `Docs/ai-audits/2026-06-17-full-architecture-audit.md` | Present |
| GODFILE | `Docs/ai-audits/2026-06-17-god-file-hunt.md` | Present |
| DEAD | `Docs/ai-audits/2026-06-17-dead-code-audit.md` | Present |
| UIRESP | `Docs/ai-audits/2026-06-17-ui-responsiveness-audit.md` | Present |
| STARTUP | `Docs/ai-audits/2026-06-17-startup-performance-investigation.md` | Present |
| MEMORY | `Docs/ai-audits/2026-06-17-memory-leak-investigation.md` | Present |
| COORD | `Docs/ai-audits/2026-06-17-network-coordinator-deep-dive.md` | Present |
| CONFIG | `Docs/ai-audits/2026-06-17-configuration-system-audit.md` | Present |
| TESTGAP | `Docs/ai-audits/2026-06-17-test-coverage-gap-analysis.md` | Present, created by this follow-up |
| JOURNEY | `Docs/ai-audits/2026-06-17-user-journey-audit.md` | Present |
| HBPARITY | `Docs/ai-audits/2026-06-17-handbrake-parity-analysis.md` | Present |
| FUTURE | `Docs/ai-audits/2026-06-17-future-feature-readiness-audit.md` | Present |
| RELIABILITY | `Docs/ai-audits/2026-06-17-reliability-audit.md` | Present |
| NERVOUS | `Docs/ai-audits/2026-06-17-make-me-nervous.md` | Present |

## Missing Or Blocked Reports

No expected report is missing after this follow-up. The original worker prompt
texts were not available as a separate prompt pack in the active audit folder,
so prompt fixes are recorded as future wording rather than applied to original
prompts.

## Normalized ID Map

This map preserves existing report text. Existing local IDs/headings should be
referenced through the normalized IDs below in the master registry and future
synthesis.

| Track | Normalized IDs | Source local IDs/headings |
|---|---|---|
| ARCH | ARCH-001 to ARCH-013 | Full Architecture findings `F-01` through `F-13` in report order. |
| GODFILE | GODFILE-001 to GODFILE-025 | Top 25 highest-risk files in God File Hunt order. |
| DEAD | DEAD-001 to DEAD-009 | Dead-code inventory groups: Python candidates; WebView candidates; PowerShell candidates; route usage candidates; duplicate/superseded implementations; stale config/settings; stale docs/tests/scripts; removal risk ranking; cleanup roadmap. |
| UIRESP | UIRESP-001 to UIRESP-010 | UI Responsiveness issues `RSP-001` through `RSP-010`. |
| STARTUP | STARTUP-001 to STARTUP-008 | Startup severity rows: Tauri pre-window validation; config import pre-listen path; initial WebView refresh queue dry-run; dev Tauri discovery; static shell blocking assets; watch-folder first cycle; duplicate snapshot/diagnostics reads; telemetry before listener. |
| MEMORY | MEMORY-001 to MEMORY-014 | Memory report risks `R1` through `R14`. |
| COORD | COORD-001 to COORD-010 | Network coordinator data-corruption/lost-work ranking rows 1 through 10. |
| CONFIG | CONFIG-001 to CONFIG-007 | Configuration risk ranking rows 1 through 7. |
| TESTGAP | TESTGAP-001 to TESTGAP-014 | Test Coverage Gap Analysis normalized findings. |
| JOURNEY | JOURNEY-001 to JOURNEY-012 | User Journey prioritized usability findings 1 through 12. |
| HBPARITY | HBPARITY-001 to HBPARITY-006 | HandBrake parity gaps 1 through 6. |
| HBPARITY | HBPARITY-007 to HBPARITY-013 | HandBrake parity improvements 1 through 7. |
| FUTURE | FUTURE-001 to FUTURE-012 | Future Feature Readiness scorecard rows from richer preset management through multi-operator access. |
| RELIABILITY | RELIABILITY-001 to RELIABILITY-010 | Reliability risks `R1` through `R10`. |
| NERVOUS | NERVOUS-001 to NERVOUS-050 | Make Me Nervous findings 1 through 50 in report order. |

## Duplicate Map

| Owner ID | Duplicate/cross-reference IDs | Title | Category | Severity | Confidence | Affected domains | Evidence source | Validation required |
|---|---|---|---|---|---|---|---|---|
| NERVOUS-001 | ARCH-013, NERVOUS-046, NERVOUS-047, NERVOUS-048, NERVOUS-050, TESTGAP-014 | Release trust and packet/worktree hygiene | Test coverage | Critical | Needs verification for current tree | change control, generated docs, release gate | Make Me Nervous, Architecture, coordinator validation | Change-control coverage, split packets, targeted tests per packet, release gate after stabilization. |
| RELIABILITY-002 | ARCH-002, JOURNEY-002, NERVOUS-020, TESTGAP-004 | Pending-publish drain and final-placement proof | Data safety | High | Confirmed | pending publish, drain, manifests, sidecars | Reliability, Architecture, Journey, Make Me Nervous | Pending-drain mutex/lease tests, dual-process fixture, pending guard smoke, real-media deferred publish/drain validation. |
| COORD-001 | COORD-002, COORD-003, COORD-004, NERVOUS-004, NERVOUS-005, NERVOUS-006, TESTGAP-003 | Network coordinator ownership, split-brain, durability, and path identity | Worker/coordinator correctness | Critical | Likely | network coordinator, worker registry, done/release, path maps | Network Deep Dive, Make Me Nervous | Owner negative tests, save-failure tests, path-normalization tests, split-brain/stale-reclaim fixtures. |
| CONFIG-001 | CONFIG-002, CONFIG-003, CONFIG-004, CONFIG-005, ARCH-010, NERVOUS-047, TESTGAP-011 | Configuration and profile drift | Configuration drift | High | Confirmed | PSD1 templates, profiles, schemas, backend metadata, WebView settings | Configuration System Audit, Architecture, Make Me Nervous | Schema parity, config key registry, settings preview/save, library profile tests, real-media for policy-affecting changes. |
| HBPARITY-002 | NERVOUS-009, NERVOUS-010, NERVOUS-012, NERVOUS-013, NERVOUS-039, TESTGAP-006 | Planned versus actual media outcome drift | Media policy | High | Likely | remux/encode, audio, subtitles, plan executor | HandBrake Parity, Make Me Nervous | Cross-engine fixture matrix, plan executor no-audio tests, MP4 audio/subtitle tests, real-media media-policy validation. |
| NERVOUS-003 | RELIABILITY queue/source movement rows, JOURNEY-001, TESTGAP-002 | Single-file launch outside configured source roots | Data safety | Critical | Likely | launch scope, source roots, queue policy | Make Me Nervous, Journey | Local API route rejection tests, command journal tests, queue launch smoke, real-media single-file validation if behavior changes. |
| NERVOUS-002 | RELIABILITY source/scratch/output rows, TESTGAP-002 | Stale partial cleanup can delete user-owned matching files | Data safety | Critical | Likely | output cleanup, staging, source/scratch/output | Make Me Nervous | Path-boundary cleanup tests, preservation tests, reliability regression, real-media publish validation if cleanup changes. |
| NERVOUS-007 | ARCH-004, TESTGAP-007 | Tauri/WebView safety validation may fail open | Startup/shutdown | Critical | Likely | Tauri shell, WebView safety fragments, command routes | Make Me Nervous, Architecture | Rust/unit safety-fragment tests, Tauri check-only, command-boundary browser smokes. |
| NERVOUS-008 | NERVOUS-033, ARCH-008, TESTGAP-005 | Command journal exception and persistence evidence gaps | Reliability | High | Likely | Local API commands, Diagnostics, command history | Make Me Nervous, Architecture | Route-exception tests, journal save-failure tests, Diagnostics/WebView command-history smoke. |
| RELIABILITY-001 | JOURNEY-001, TESTGAP-014 | Priority/hold manifest fail-open risk | Queue correctness | High | Confirmed | queue priority, hold manifest, launch planning | Reliability | Corrupt/truncated/locked manifest tests, queue preview fail-closed smoke, launch preflight blocker test. |
| RELIABILITY-003 | STARTUP-003, JOURNEY-009, TESTGAP-008 | Queue source scans can stall close readiness | Startup/shutdown | High | Confirmed | queue scans, close readiness, filesystem roots | Reliability, Startup, Journey | Blocking fake scanner tests, stale scan close-readiness tests, unavailable-root smoke. |
| RELIABILITY-004 | MEMORY resource rows, TESTGAP-009 | Long subprocess timeouts can stall a run | Performance | Medium | Confirmed | FFmpeg, OCR, robocopy, native tools | Reliability, Memory | Fake hanging native-tool tests, no-progress watchdog tests, retry/quarantine tests, corrupt-media validation if behavior changes. |
| RELIABILITY-005 | ARCH-004, NERVOUS-035, TESTGAP-007 | Forced active-work shutdown is not safe unattended recovery | Data safety | High | Confirmed | shutdown, ActiveJobs, process control, Tauri close | Reliability, Make Me Nervous | Adversarial kill tests for encode/remux/copy/drain, close-readiness tests, live close validation. |
| RELIABILITY-006 | MEMORY-010, MEMORY-012, NERVOUS-041, TESTGAP-009 | Forensic evidence can age out or drift | Reliability | Medium | Confirmed | command journal, logs, SQLite mirror, JSON authority | Reliability, Memory, Make Me Nervous | Retention tests, SQLite drift/rebuild tests, Diagnostics degraded-persistence smoke. |
| STARTUP-001 | STARTUP-002, STARTUP-003, ARCH-004, TESTGAP-008 | Startup has too much pre-readiness blocking work | Performance | High | Confirmed | launchers, Local API, Tauri, WebView first refresh | Startup, Architecture | Startup timing instrumentation, Local API/Tauri smokes, slow route injection, first-load smoke. |
| MEMORY-001 | MEMORY-003, MEMORY-005, MEMORY-010, MEMORY-012, TESTGAP-009 | Long-run listeners, threads, and process handles need leak proof | Reliability | Medium | Likely | WebView bootstrap, rename, network logs, process wrappers, Tauri monitors | Memory Leak Investigation | Duplicate-init smoke, handler idempotency tests, handle-count checks, coordinator churn soak. |
| UIRESP-001 | UIRESP-002, UIRESP-003, UIRESP-004, UIRESP-006, UIRESP-007, TESTGAP-010 | UI commands need consistent in-flight, stale-result, and timeout handling | UI feedback/usability | High | Confirmed | network, queue, schedule, reports, sample validation, API client | UI Responsiveness | Browser/API double-click tests, hung POST smoke, stale response token tests, accessibility busy-state checks. |
| JOURNEY-001 | JOURNEY-003, JOURNEY-008, JOURNEY-009, UIRESP-008 | Operator scope and readiness wording can mislead | Documentation/operator guidance | High | Confirmed | Queue, Launch, Pending Publish, docs, verification commands | User Journey, UI Responsiveness | Browser/copy review, docs link checks, no-mutation UI smokes for changed surfaces. |
| GODFILE-001 | GODFILE-002, GODFILE-003, ARCH-008, TESTGAP-012 | Large active files are high-blast-radius maintenance risks | Maintainability | Medium | Confirmed | WebView network/queue, core network facade, pipeline entrypoints | God File Hunt, Architecture | Prework checks, focused tests by touched domain, route ownership guard, browser smokes when UI changes. |
| DEAD-001 | DEAD-002, DEAD-003, DEAD-004, DEAD-005, TESTGAP-012 | Dead/stale candidates need removal-proof validation | Dead code/stale surface | Medium | Confirmed | WebView helpers, PowerShell helpers, routes, compatibility shims | Dead Code Audit | Exact reference scans, route logging, focused smokes, package import tests, owner approval before removal. |
| FUTURE-001 | FUTURE-002, FUTURE-006, FUTURE-010, FUTURE-011, FUTURE-012 | Future remote/distributed features need durable state and auth first | Future scalability | High | Confirmed | distributed workers, remote management, cloud sync, plugins, multi-operator | Future Feature Readiness | Read-only contracts, dry-runs, durable state design, remote auth/RBAC validation, provider tests. |

## Master Issue Registry

| Global ID | Source audit ID | Owning audit | Title | Category | Severity | Confidence | Affected files/domains | Evidence | Duplicate/cross-reference IDs | Recommended action | Validation required | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AUDIT-001 | NERVOUS-001 | NERVOUS | Stabilize worktree and packet evidence before trusting validation | Test coverage | Critical | Needs verification | change control, generated evidence, release gates | Make Me Nervous rank 1 and findings 46-50 | ARCH-013, TESTGAP-014 | Build packet-to-file coverage map and split or close stale packets before release claims. | `validate_changes --require-worktree-coverage`, targeted tests per packet, full release gate after stabilization. | Open |
| AUDIT-002 | NERVOUS-002 | RELIABILITY | Stale partial cleanup may delete user-owned matching files | Data safety | Critical | Likely | source/scratch/output cleanup | Make Me Nervous finding 2 | TESTGAP-002 | Constrain cleanup to pipeline-owned artifacts with provenance. | Preservation tests, path-boundary cleanup tests, reliability regression, real-media publish validation if behavior changes. | Open |
| AUDIT-003 | NERVOUS-003 | RELIABILITY | Single-file launch can process files outside configured roots | Data safety | Critical | Likely | launch scope, source roots, queue | Make Me Nervous finding 3 | JOURNEY-001, TESTGAP-002 | Require supported media under configured roots or explicit profile roots. | Local API tests, command-journal tests, queue launch smoke, real-media single-file validation if behavior changes. | Open |
| AUDIT-004 | COORD-001 | COORD | Network coordinator split-brain and ownership risks | Worker/coordinator correctness | Critical | Likely | coordinator, worker claims, done/release, path identity | Network ranking and Make Me Nervous findings 4-6 | NERVOUS-004, NERVOUS-005, NERVOUS-006, TESTGAP-003 | Enforce identity, durable terminal acceptance, and canonical source identity before broader network rollout. | Adversarial endpoint tests, save-failure tests, path-normalization tests, split-brain/stale-reclaim fixtures. | Open |
| AUDIT-005 | RELIABILITY-002 | RELIABILITY | Pending-publish drain lacks visible global mutex | Data safety | High | Confirmed | pending publish, drain, manifests, sidecars | Reliability R2 | ARCH-002, JOURNEY-002, TESTGAP-004 | Add global drain lease/mutex before concurrent drain paths expand. | Mutex/lease tests, dual-process fixture, pending guard smoke, deferred-publish real-media validation. | Open |
| AUDIT-006 | NERVOUS-007 | RELIABILITY | Tauri/WebView safety validation should fail closed | Startup/shutdown | Critical | Likely | Tauri, WebView validation, command routes | Make Me Nervous finding 7 | ARCH-004, TESTGAP-007 | Classify fatal safety checks and quarantine or block mutation when missing. | Rust/unit fragment tests, Tauri check-only, command-boundary browser smokes. | Open |
| AUDIT-007 | NERVOUS-008 | RELIABILITY | Command route exceptions can be absent from durable journal | Reliability | High | Likely | Local API, command journal, Diagnostics | Make Me Nervous finding 8 | NERVOUS-033, TESTGAP-005 | Journal sanitized failed command rows for route exceptions and surface persistence degradation. | Route-exception tests, journal save-failure tests, command-history smoke. | Open |
| AUDIT-008 | HBPARITY-002 | HBPARITY | Planned versus actual media outcomes are spread and can drift | Media policy | High | Likely | route decisions, audio, subtitles, plan executor | HandBrake parity gap 2 and Make Me Nervous media findings | NERVOUS-009, NERVOUS-010, NERVOUS-012, NERVOUS-013, NERVOUS-039, TESTGAP-006 | Build cross-engine parity matrix before changing media behavior. | Python/PowerShell parity tests, plan executor tests, MP4 audio/subtitle tests, real-media samples. | Open |
| AUDIT-009 | CONFIG-001 | CONFIG | Config and profile source-of-truth split can change policy silently | Configuration drift | High | Confirmed | config schema, Default profile, LibraryProfiles, LocalBase overlays | Configuration audit risk ranking | ARCH-010, NERVOUS-047, TESTGAP-011 | Reconcile schema/profile/default parity in focused packets. | Config registry/schema tests, settings preview/save tests, profile tests, real-media for policy keys. | Open |
| AUDIT-010 | RELIABILITY-001 | RELIABILITY | Priority/hold manifest corruption can fail open | Queue correctness | High | Confirmed | priority manifest, queue launch | Reliability R1 | TESTGAP-014 | Fixed in `MP-CHANGE-2026-0618-005`: unreadable manifests fail closed for Python preview/API/update and PowerShell queue-entry planning; explicit clear-all remains the recovery path. | Corrupt manifest Python tests, Local API read test, queue preview blocker test, and PowerShell queue engine check. | Fixed |
| AUDIT-011 | RELIABILITY-003 | RELIABILITY | Queue source scans can stall close readiness | Startup/shutdown | High | Confirmed | queue scan, close readiness, filesystem roots | Reliability R3 and Startup ranking | STARTUP-003, TESTGAP-008 | Bound or isolate scans and expose stale-scan recovery. | Fake blocking scanner tests, stale scan close-readiness tests, unavailable-root smoke. | Open |
| AUDIT-012 | RELIABILITY-004 | RELIABILITY | Long subprocess timeouts can stall useful queue work | Performance | Medium | Confirmed | FFmpeg, OCR, robocopy, native process | Reliability R4 | MEMORY resource rows | Add no-progress watchdogs and retry/quarantine budgets before unattended reliance. | Fake native-tool tests, no-progress tests, retry/quarantine tests. | Open |
| AUDIT-013 | RELIABILITY-005 | RELIABILITY | Forced active-work shutdown is unsafe as routine recovery | Data safety | High | Confirmed | shutdown, process control, ActiveJobs, Tauri close | Reliability R5 | NERVOUS-035, TESTGAP-007 | Keep force shutdown exceptional and add post-force recovery scan. | Kill-during-work tests, close-readiness tests, live active-work close validation. | Open |
| AUDIT-014 | RELIABILITY-006 | RELIABILITY | Forensic evidence can age out or drift | Reliability | Medium | Confirmed | command journal, logs, SQLite mirror, JSON state | Reliability R6 | NERVOUS-041, TESTGAP-009 | Extend retention or add daily durable summaries and drift checks. | Retention tests, SQLite drift/rebuild tests, Diagnostics degraded-persistence smoke. | Open |
| AUDIT-015 | STARTUP-001 | STARTUP | Startup first paint and API readiness have expensive prework | Performance | High | Confirmed | launchers, Tauri, Local API, WebView first refresh | Startup severity ranking | ARCH-004, TESTGAP-008 | Instrument before changing, then split critical readiness from heavy evidence. | Startup timing smokes, slow route injection, Local API/Tauri smoke. | Open |
| AUDIT-016 | MEMORY-001 | MEMORY | Long-run listener/thread/process resource cleanup needs proof | Reliability | Medium | Likely | WebView, Tauri, network, PowerShell native wrappers | Memory report R1-R14 | TESTGAP-009 | Add idempotency guards and resource lifetime instrumentation where confirmed. | Duplicate init smoke, handler idempotency tests, handle-count checks, churn soak. | Open |
| AUDIT-017 | UIRESP-001 | UIRESP | UI command surfaces need consistent in-flight and stale-response handling | UI feedback/usability | High | Confirmed | network, queue, schedule, reports, sample validation, API client | UI Responsiveness RSP-001 to RSP-010 | JOURNEY-001, TESTGAP-010 | Add command locks and stale response tokens while preserving backend authority. | Browser double-click tests, hung POST smoke, accessibility busy-state tests. | Open |
| AUDIT-018 | JOURNEY-001 | JOURNEY | Operator backend scope is hard to understand | Documentation/operator guidance | High | Confirmed | Queue, Launch, Pending Publish, verification docs | User Journey prioritized findings | UIRESP-008 | Add clearer scope/readiness labels without changing backend behavior. | Docs checks, UI no-mutation smokes if copy changes visible surfaces. | Open |
| AUDIT-019 | GODFILE-001 | GODFILE | High-blast-radius active files need careful extraction sequencing | Maintainability | Medium | Confirmed | WebView network/queue, core network facade, entrypoints | God File Hunt top files | ARCH-008, TESTGAP-012 | Extract only after specialist correctness fixes and focused tests. | WebView prework/check, route ownership guard, domain tests, browser smokes for UI changes. | Open |
| AUDIT-020 | DEAD-001 | DEAD | Dead-code removals need owner validation and smoke proof | Dead code/stale surface | Medium | Confirmed | WebView helpers, PowerShell helpers, routes, compatibility shims | Dead Code Audit inventories | GODFILE, TESTGAP-012 | Remove only low-risk confirmed dead code in small packets. | Exact reference scans, route logging, focused smokes, package import tests. | Open |
| AUDIT-021 | FUTURE-010 | FUTURE | Cloud sync, plugins, multi-operator, and remote mutation are not ready | Future scalability | High | Confirmed | durable state, auth/RBAC, provider abstraction, mutation routes | Future Readiness scorecard and blockers | ARCH-011, COORD, CONFIG, RELIABILITY | Add read-only evidence and dry-runs before durable state and mutation. | Read-only contracts, dry-runs, durable-state tests, remote auth/RBAC validation. | Open |
| AUDIT-022 | RELIABILITY-008 | RELIABILITY | Network mode is provider-guarded, not unattended production-ready | Worker/coordinator correctness | High | Confirmed | network lifecycle, provider hooks, close readiness | Reliability R8, current state docs | COORD, FUTURE | Keep network mode out of unattended production until provider and recovery gates are complete. | Lifecycle tests, duplicate start/stop tests, crash/done replay tests, simulated network soak. | Open |
| AUDIT-023 | HBPARITY-001 | HBPARITY | HandBrake-style preview and inspection gaps reduce operator confidence | UI feedback/usability | Medium | Confirmed | preview encode, per-file decision review, output inspection | HandBrake parity gaps/improvements | JOURNEY-006, UIRESP | Build read-only inspection packets before adding media-transforming previews. | API fixture tests, WebView smokes, real-media validation if FFmpeg behavior changes. | Open |
| AUDIT-024 | NERVOUS-045 | TESTGAP | Representative real-media validation is attested but not reproducible from repo alone | Test coverage | High | Confirmed | real-media evidence, release confidence | Make Me Nervous finding 45, current checklist | TESTGAP-006, TESTGAP-014 | Maintain a rerunnable redacted sample matrix or operator-run checklist. | Real-media remux, encode/size, subtitle, audio, deferred publish, drain after high-risk changes. | Open |
| AUDIT-025 | NERVOUS-048 | TESTGAP | Generated summaries and project index can drift during large changes | Maintainability | Medium | Confirmed | generated summaries, project index, AI navigation | Make Me Nervous finding 48 | ARCH-012 | Refresh/check summaries after stabilizing source/doc packets. | `refresh_summaries --check`, project index check, summary integrity tests. | Open |

## Prompt Issue Disposition

| Coordinator prompt issue | Disposition | Future wording | Existing reports needing manual normalization |
|---|---|---|---|
| No shared finding ID scheme | Resolved for synthesis | "Use `<TRACK>-NNN` IDs and list duplicate/cross-reference IDs." | All existing reports are mapped here, not rewritten. |
| Severity/category taxonomy not shared | Resolved for synthesis | "Use coordinator Critical/High/Medium/Low and category list." | Existing reports may retain local labels. |
| Duplicate specialist analysis | Resolved for synthesis | "Cite the owning ID and add only new evidence or impact." | NERVOUS and ARCH remain duplicate-rich by design. |
| Prompts may allow implementation drift | Resolved for future prompts | "Report-only unless explicitly authorized; do not modify runtime behavior." | No existing report was edited. |
| Evidence requirements vary | Partially resolved | "Every finding includes evidence, confidence, affected domains, owner, validation required, and whether dynamic validation ran." | Existing reports vary; registry normalizes top issues. |
| Summaries-before-source rule | Resolved for future prompts | "Read generated summary before full source when available and record why full source was needed." | Existing reports not retrofitted. |
| Lifecycle ownership overlap | Resolved for synthesis | "ARCH diagrams; STARTUP timing; RELIABILITY failures; MEMORY leaks; COORD protocol." | Existing overlaps mapped in duplicate map. |
| Settings UI/backend config overlap | Resolved for synthesis | "CONFIG owns semantics; UI/JOURNEY own display and comprehension." | Existing overlaps mapped. |
| Risk synthesis overlap | Resolved with owner rule | "NERVOUS is an escalation lens, not default root-cause owner." | NERVOUS items preserved as cross-references. |
| Missing TESTGAP output | Resolved | "Write `Docs/ai-audits/2026-06-17-test-coverage-gap-analysis.md`." | TESTGAP report added. |
| God/dead code overreach | Resolved for future prompts | "Do not remove without owner, evidence, rollback, and validation rung." | GODFILE/DEAD are not implementation plans. |
| UI may recommend frontend mutation | Resolved for future prompts | "All UI recommendations preserve backend-owned mutation and policy authority." | UIRESP/JOURNEY recommendations remain docs-only. |
| Network/Future duplicate current defects | Resolved for synthesis | "COORD owns current network correctness; FUTURE explains blockers." | FUTURE rows cite COORD as dependency. |
| Runtime tests or long runs implied | Resolved for future prompts | "State static-only; do not start services or run media without authorization." | Existing static-only limitations preserved. |
| HandBrake parity may be mistaken for defects | Resolved for synthesis | "Separate intentional differences, operator-value gaps, and safety defects." | HBPARITY mapped as parity owner, not root-cause owner for safety defects. |
| Dead code generated/archive compatibility risk | Resolved for future prompts | "Classify generated, archived, compatibility, dead, or unknown before removal." | DEAD remains candidate inventory only. |
| Missing duplicate map section | Resolved | "Add a cross-reference and possible duplicates section." | This file contains the duplicate map. |
| Missing validation ladder language | Resolved for registry | "Name smallest safe validation rung and call out real-media needs." | Registry and TESTGAP include validation. |

## Severity Conflicts

| Issue | Severity conflict | Provisional resolution |
|---|---|---|
| Network mode readiness | FUTURE rates distributed workers as medium-high readiness risk; RELIABILITY and COORD identify critical/high failure modes. | Keep current-state defects under COORD/RELIABILITY as Critical/High; FUTURE remains a roadmap dependency. |
| Media parity gaps | HBPARITY frames some gaps as operator-value improvements; NERVOUS escalates selected audio/subtitle drift to High. | Keep parity UI/product gaps as Medium unless they can produce silent wrong output; keep no-audio/subtitle/audio selection as High until validated. |
| Worktree hygiene | Current `git status` may differ from Make Me Nervous evidence. | Keep NERVOUS-001 as Needs verification until current packet/worktree state is audited. |
| Dead-code candidates | DEAD marks some candidates low or medium; GODFILE marks surrounding files high blast radius. | Keep deletion risk based on touched domain, not just unused evidence. |
| UI scope confusion | JOURNEY rates operator scope confusion High; UIRESP may rate underlying stale markers Medium. | Keep operator-scope misunderstanding High because wrong action scope can lead to unsafe launch/drain decisions. |

## Insufficient-Evidence Findings

| Finding | Why insufficient | First evidence step |
|---|---|---|
| NERVOUS-004 through NERVOUS-006 | Marked Needs verification against possibly changing network source. | Inspect current network source through summaries first, then add owner/durability/path tests. |
| NERVOUS-035 | Live Tauri active-work close behavior lacks automated live proof. | Create a controlled release-gated PG-1 live close harness or record manual evidence. |
| NERVOUS-045 | Real-media evidence is operator-attested and not fully reproducible from checkout. | Maintain a redacted sample matrix and rerun after high-risk media changes. |
| ARCH-012 | Generated summaries incomplete for some high-value files, but exact current scope may change with summary refresh. | Run summary check after source/doc packets stabilize. |
| DEAD route/caller candidates | Static route searches can miss dynamic construction or generated indirection. | Use route logging and browser/API smokes before removal or inventory edits. |

## Recommended Remediation Order

1. Stabilize release trust: reconcile packet coverage, generated summaries, and current validation evidence.
2. Validate data-safety risks: stale cleanup, single-file source-root enforcement, pending drain concurrency, and command journal exceptions.
3. Harden network correctness: split-brain prevention, worker ownership, durable terminal reports, path identity, stale reclaim, and worker crash recovery.
4. Reconcile media policy: audio/subtitle/no-audio/default profile parity across Python and PowerShell before changing FFmpeg/subtitle/audio behavior.
5. Reconcile configuration drift: schema/template/profile/library/runtime-overlay parity in narrow packets.
6. Improve startup/shutdown and long-run reliability: instrumentation first, then bounded scans, watchdogs, retention, and recovery flows.
7. Improve UI/operator trust: command busy states, stale markers, scope language, readiness labels, and restart lanes while preserving backend authority.
8. Reduce maintenance blast radius: god-file extraction and dead-code cleanup only after owner-specific validation.
9. Prepare future features: read-only evidence, dry-runs, durable state, and remote auth/RBAC before any off-host or multi-operator mutation.

## Validation Ladder For Top Issues

| Issue | Smallest safe validation rung |
|---|---|
| Worktree/packet trust | Change-control validation, summary/project-index checks, targeted tests per retained packet. |
| Stale cleanup/source-root launch | Path-boundary unit tests, Local API route tests, queue launch smoke, real-media if behavior changes. |
| Network ownership/durability/path identity | Network unit/API tests, crash recovery tests, simulated multi-worker workflow, manual multi-machine only after local simulation. |
| Pending-publish drain | Pending-publish unit tests, dual-process fixture, pending-drain WebView smoke, real-media deferred-publish/drain after behavior changes. |
| Command journal exceptions | Local API command tests, strict JSON/route exception tests, WebView command-history smoke. |
| Media policy parity | Python/PowerShell parity tests, PowerShell media-policy tests, integration matrix, representative real-media samples. |
| Tauri fail-closed close/readiness | Rust/unit tests, Tauri check-only, browser no-mutation/command-boundary smoke, live active-work close evidence if lifecycle changes. |
| Config/profile drift | Config schema and registry tests, settings preview/save tests, LibraryProfiles tests, real-media for media-policy defaults. |
| UI responsiveness | Browser/API mock smokes for double-click, hung POST, stale result, panel stale/error markers, accessibility busy state. |
| God/dead cleanup | Exact reference scans, focused unit/static tests, browser smokes for visible UI, package import smoke for compatibility layers. |

## Resolved Open Questions

| Coordinator question | Answer |
|---|---|
| Where is the Test Coverage Gap Analysis report, and should synthesis wait? | It was missing. This follow-up created `Docs/ai-audits/2026-06-17-test-coverage-gap-analysis.md`, so synthesis no longer needs to wait for a missing file. |
| Should existing reports be edited to adopt the shared ID scheme? | No. This registry maps existing local IDs/headings to normalized IDs without rewriting worker reports. |
| Should the coordinator produce the final synthesis as a separate report? | Yes. This bounded master registry is the final synthesis aid requested by the follow-up task. |
| Should NERVOUS severity upgrades require specialist-owner approval? | Yes for final remediation severity. They may drive provisional roadmap priority, but specialist owner review should settle final root-cause severity. |
| Should future prompt packs be stored in `docs/ai-audits/`? | Needs operator direction. Default recommendation: keep prompt packs outside active docs or store them as bounded audit evidence, not as a new single source of truth. |

## Open Operator Decisions

1. Decide whether future prompt packs should be checked into `Docs/ai-audits`
   or kept outside the repository.
2. Decide whether to retrofit existing audit reports with normalized IDs, or
   preserve this registry as the mapping layer. Recommendation: preserve the
   registry only.
3. Decide whether NERVOUS-prioritized issues should become backlog entries in
   `docs/OPEN_WORK_CHECKLIST.md` after specialist owner review.
4. Decide whether real-media evidence should remain attestation-only or gain a
   redacted rerunnable sample matrix.

## Limitations

- No source behavior, tests, launchers, schemas, generated contracts, runtime
  config, or operator workflows were changed.
- This synthesis did not run the test suite, browser smokes, release gate,
  Tauri shell, Local API server, FFmpeg, or real-media validation.
- This synthesis does not prove every worker finding is still present in the
  latest worktree. Findings marked Likely or Needs verification require owner
  validation before implementation.
- Existing worker reports were not edited. Normalization is by registry map.
