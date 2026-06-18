# Remediation Plan

This plan is ordered by authority-boundary risk. It does not implement source changes in this review packet.

## P0: Fail Closed On Safety-Critical WebView Validation Drift

Finding: F-01.

Objective:

The normal WebView shell must not open with mutation-capable controls when Tauri detects missing safety-critical assets.

Recommended implementation:

1. Classify WebView validation fragments by severity in Tauri validation code.
2. Make these fragment failures fatal before opening the normal shell:
   - Close-readiness load and unsafe-shutdown disabled guard.
   - Backend shutdown button guard.
   - Route contract load/validation.
   - Network lifecycle contract/precondition guard.
   - Pending publish drain backend-authority guard.
   - Rename fresh-preview and confirmation guard.
   - Settings preview/save confirmation guard.
   - Token bootstrap and placeholder safety.
3. If diagnostics must remain available, open a diagnostics-only shell with all mutation/process/lifecycle controls disabled.
4. Update startup warning copy so warnings are informational, not the primary safety mechanism.
5. Add regression tests that remove each safety fragment and assert fail-closed behavior.

Acceptance criteria:

- Missing close-readiness or shutdown guard prevents the normal shell from opening.
- Missing route-contract, pending-drain, network, rename, or settings guard prevents mutation-capable shell controls.
- Tests no longer assert that non-bootstrap safety drift is generally nonfatal.

## P1: Represent Active Stop As Draining Or Active-Work-Preserved

Finding: F-02.

Objective:

Network lifecycle stop results must not tell the operator the system is stopped while active work remains preserved.

Recommended implementation:

1. Extend provider/facade result payload to identify active-work-preserved stop outcomes.
2. Use a distinct `state_after.status`, such as `draining`, `stop_requested`, or `active_work_preserved`, when runtime entries, active jobs, active claims, or preserved processes remain.
3. Preserve current media-safety behavior: do not kill active work during ordinary stop.
4. Update WebView rendering to headline the pending/preserved state.
5. Add backend tests for active local worker, active coordinator/local worker, and remote claims.
6. Add WebView browser/stub tests that active-stop evidence does not render plain stopped success.

Acceptance criteria:

- Active work preservation cannot produce plain stopped evidence.
- Operator sees that stop was requested and active work remains.
- Journal evidence includes preserved work state.

## P1: Harden WebView Token And CSP Boundaries

Finding: F-03.

Objective:

Reduce the authority of arbitrary script execution inside the WebView.

Recommended implementation:

1. Keep the Local API token out of readable global bootstrap state where practical.
2. Initialize API client from Tauri bootstrap and then erase or freeze minimal non-secret metadata.
3. Avoid globally exposing broad tokened `apiPost` helpers, or expose only narrow command wrappers.
4. Remove `'unsafe-eval'`; reduce `'unsafe-inline'` after replacing inline bootstrap/script needs.
5. Consider route/effect-scoped command capabilities for high-risk mutations.
6. Add browser/static tests for token non-exposure and CSP regressions.

Acceptance criteria:

- Token is not readable from `window.MEDIA_PIPELINE_BOOTSTRAP`.
- Tokened command functions are not broad globals unless explicitly justified.
- Browser and Tauri static validation still pass.

## P2: Resolve Cross-Platform Single-Instance Boundary

Finding: F-04.

Objective:

Prevent multiple shells from owning shared backend state, or document/package Windows-only support.

Recommended implementation:

1. If shipping non-Windows, add cross-platform lockfile/advisory lock ownership before backend start.
2. If not shipping non-Windows, restrict `bundle.targets` and release docs to Windows.
3. Add tests for second-instance behavior on supported targets.

Acceptance criteria:

- Supported targets have an enforced single-instance guard.
- Unsupported targets are not advertised by package configuration.

## P2: Keep Debug Automation Release-Fenced

Finding: F-05.

Objective:

Ensure test automation cannot bypass operator confirmation in production bundles.

Recommended implementation:

1. Keep debug automation behind debug compilation and explicit environment flags.
2. Add release-profile tests or build checks that the debug automation paths are inert.
3. Keep PG harness docs clear that confirmation override is test-only.

Acceptance criteria:

- Release builds cannot run debug autolaunch or confirmation override.
- Debug tests continue to work through explicit harness flags.

## Ongoing Controls

Maintain:

- Local API route contract tests.
- Command payload strictness tests.
- WebView no-direct-filesystem static checks.
- Backend-owned queue/publish/rename/settings/final-library tests.
- Generated summary refresh for changed docs/source.
- Change-control packets for meaningful review/remediation changes.
