# Test Coverage Gap Analysis - 2026-06-17

Change packet: `MP-CHANGE-2026-0618-001`

This report closes the missing TESTGAP track identified by
`docs/ai-audits/2026-06-17-audit-coordinator.md`. It is a coordination report,
not an independent source-code audit. It does not run tests, execute media
processing, start services, edit tests, or validate current runtime behavior.

## Executive Summary

The audit set already contains many validation requirements, but before this
report there was no TESTGAP owner to normalize them. The highest-priority
coverage gaps are:

1. Data-safety and source-path tests for stale partial cleanup and single-file
   launch outside configured source roots.
2. Network coordinator adversarial tests for worker identity, durable done
   acceptance, path identity normalization, split-brain, stale reclaim, and
   worker crash recovery.
3. Pending-publish dual-drain and final-placement evidence tests.
4. Command journal exception and persistence-failure tests.
5. Media-policy parity tests across Python preview/planner and PowerShell
   runtime, including no-audio, MP4 audio selection, subtitle reduction, and
   default audio profile behavior.
6. Tauri/WebView fail-closed and live active-work close validation.
7. Startup, memory, UI responsiveness, config drift, and dead-code removal
   tests that should gate lower-risk cleanup and usability work.

## Methodology

Evidence sources:

- `Docs/ai-audits/2026-06-17-audit-coordinator.md`
- `Docs/ai-audits/2026-06-17-make-me-nervous.md`
- `Docs/ai-audits/2026-06-17-reliability-audit.md`
- `Docs/ai-audits/2026-06-17-network-coordinator-deep-dive.md`
- `Docs/ai-audits/2026-06-17-startup-performance-investigation.md`
- `Docs/ai-audits/2026-06-17-memory-leak-investigation.md`
- `Docs/ai-audits/2026-06-17-ui-responsiveness-audit.md`
- `Docs/ai-audits/2026-06-17-configuration-system-audit.md`
- `Docs/ai-audits/2026-06-17-handbrake-parity-analysis.md`
- `Docs/ai-audits/2026-06-17-dead-code-audit.md`
- `Docs/ai-audits/2026-06-17-god-file-hunt.md`
- `Docs/ai-audits/2026-06-17-user-journey-audit.md`
- `Docs/ai-audits/2026-06-17-future-feature-readiness-audit.md`

No full source files were opened for this report. Findings below are
coordination findings derived from existing audit evidence and should be
validated by the owning implementation worker before remediation.

## Normalized TESTGAP Findings

| ID | Title | Category | Severity | Confidence | Evidence source | Validation required | Status |
|---|---|---|---|---|---|---|---|
| TESTGAP-001 | Missing original Test Coverage Gap Analysis report | Test coverage | High | Confirmed | Coordinator report listed the track as missing from `docs/ai-audits`. | This report plus master registry coverage validation. | Resolved by this report for coordination; still needs implementation-owner review. |
| TESTGAP-002 | Data-safety cleanup and source-root enforcement tests | Data safety | Critical | Likely | Make Me Nervous findings on stale partial cleanup and single-file launch outside roots. | Path-boundary cleanup tests, Local API launch-route tests, command-journal tests, queue launch smoke, representative real-media single-file validation if behavior changes. | Open |
| TESTGAP-003 | Network worker ownership, durability, and path identity tests | Worker/coordinator correctness | Critical | Likely | Make Me Nervous network ownerless done/release, durable done acceptance, raw path identity, worker crash, and Network Coordinator split-brain rankings. | Negative endpoint tests for missing/empty worker id, save-failure tests, Windows/UNC path-normalization tests, split-brain/stale-reclaim fixtures, worker crash recovery tests, simulated multi-worker validation. | Open |
| TESTGAP-004 | Pending-publish dual-drain and final-placement proof tests | Data safety | High | Confirmed | Reliability R2 and architecture pending-publish state-machine findings. | Named mutex/lease tests if implemented, dual-process pending-drain fixture, pending drain WebView guard smoke, representative deferred-publish plus drain validation. | Open |
| TESTGAP-005 | Command journal exception and persistence degradation tests | Reliability | High | Likely | Make Me Nervous command-route exception and journal persistence findings. | Route-exception regression proving `/api/commands` failed rows, JSON-save failure tests, SQLite mirror failure/degraded tests, WebView command-history smoke. | Open |
| TESTGAP-006 | Media-policy parity and no-audio/subtitle reduction tests | Media policy | High | Likely | Make Me Nervous audio/subtitle findings and HandBrake parity validation matrix. | Python/PowerShell route/audio/subtitle parity fixtures, plan-executor no-audio tests, MP4 audio selection tests, subtitle sidecar/reduction tests, real-media multi-audio/subtitle validation for behavior changes. | Open |
| TESTGAP-007 | Tauri/WebView fail-closed and live close validation | Startup/shutdown | High | Likely | Make Me Nervous Tauri fail-open after safety warnings and live active-work close gap. | Rust/unit safety-fragment tests, Tauri check-only, browser command-boundary smokes, controlled live active-work close validation or release-gated manual PG-1 evidence. | Open |
| TESTGAP-008 | Startup timing and pre-readiness instrumentation tests | Performance | Medium | Confirmed | Startup report severity ranking for Tauri pre-window validation, config import, initial refresh queue dry-run, asset loading, and watch first-cycle contention. | Local API startup smoke with timing evidence, Tauri startup timing smoke, slow optional-route injection, launcher fallback checks, first-load WebView smoke. | Open |
| TESTGAP-009 | Memory and long-run resource-retention tests | Reliability | Medium | Likely | Memory report R1-R14 and long-run scenarios. | Duplicate bootstrap listener/timer smoke, rename init idempotency smoke, thread/process handle leak checks, coordinator churn soak, diagnostics large-directory scan test. | Open |
| TESTGAP-010 | UI double-submit, stale result, and hidden failure tests | UI feedback/usability | Medium | Confirmed | UI Responsiveness RSP-001 through RSP-010. | Slow API/browser double-click smokes for network, queue, schedule, reports, sample validation, hung POST handling, per-panel stale/error banner tests, accessibility busy-state smoke. | Open |
| TESTGAP-011 | Config/schema/profile/runtime-overlay parity tests | Configuration drift | High | Confirmed | Configuration audit risk ranking for network key split, default profile drift, LibraryProfiles mirroring, schema differences, and LocalBase overlays. | Config schema parity checks, PowerShell config key registry checks, settings preview/save tests, library profile tests, default profile/template comparison, real-media validation for policy-affecting changes. | Open |
| TESTGAP-012 | Dead-code and god-file cleanup guard tests | Maintainability | Medium | Confirmed | Dead Code Audit removal-risk ranking and God File Hunt validation recommendations. | Exact reference scans, route logging where dynamic routes are suspected, focused WebView/static/browser smokes, dependency boundary checks, package import smoke, no behavior removal without owner approval. | Open |
| TESTGAP-013 | Future feature readiness validation gates | Future scalability | Medium | Confirmed | Future Feature Readiness scorecard and sequencing. | Read-only evidence contracts before mutation, scheduler dry-run tests, durable state design tests, remote auth/RBAC validation, provider test-send/dry-run fixtures, real-media validation for media-transforming features. | Open |
| TESTGAP-014 | Current release-gate proof after worktree stabilization | Test coverage | High | Needs verification | Make Me Nervous finding that current dirty-tree proof was not current at audit time; current status may change as packets are reconciled. | Change-control coverage validation, targeted tests per retained packet, full release gate, Tauri/package validation when launcher/package surfaces change, real-media validation for high-risk media changes. | Open |

## Cross-References To Owning Findings

| TESTGAP ID | Owning source issue(s) to validate |
|---|---|
| TESTGAP-002 | NERVOUS-002, NERVOUS-003, RELIABILITY source/scratch/output rows, JOURNEY-001 |
| TESTGAP-003 | COORD-001 through COORD-010, NERVOUS-004 through NERVOUS-006, RELIABILITY-008 |
| TESTGAP-004 | RELIABILITY-002, ARCH-002, JOURNEY-002, NERVOUS-020 |
| TESTGAP-005 | NERVOUS-008, NERVOUS-033, ARCH-008 |
| TESTGAP-006 | HBPARITY-002 through HBPARITY-004, CONFIG-002, NERVOUS-009 through NERVOUS-015, NERVOUS-039 |
| TESTGAP-007 | NERVOUS-007, NERVOUS-035, ARCH-004 |
| TESTGAP-008 | STARTUP-001 through STARTUP-008, ARCH-004 |
| TESTGAP-009 | MEMORY-001 through MEMORY-014, RELIABILITY-006 through RELIABILITY-008 |
| TESTGAP-010 | UIRESP-001 through UIRESP-010, JOURNEY-001, JOURNEY-009 |
| TESTGAP-011 | CONFIG-001 through CONFIG-007, ARCH-010, NERVOUS-047 |
| TESTGAP-012 | GODFILE-001 through GODFILE-025, DEAD-001 through DEAD-009 |
| TESTGAP-013 | FUTURE-001 through FUTURE-012 |
| TESTGAP-014 | NERVOUS-001, NERVOUS-046 through NERVOUS-050 |

## Coverage Ownership Rules

- Specialist audits own source-code root cause.
- TESTGAP owns missing validation, weak assertions, stale tests, smoke gaps,
  and real-media evidence requirements.
- If a future implementation fixes source behavior and tests in one packet, the
  source finding should remain owned by the specialist track, while TESTGAP is
  marked resolved only after the required validation evidence is present.
- Real-media validation is required after FFmpeg/media-policy, subtitle, audio,
  publish/drain, source/scratch/output movement, or cleanup behavior changes.

## Limitations

- This report did not run the test suite.
- This report did not inspect full source files.
- This report does not prove that a gap still exists in the latest dirty or
  staged worktree; it records coordination gaps from the audit evidence.
- Any implementation must use a separate change packet and the validation rung
  appropriate to the touched runtime surface.
