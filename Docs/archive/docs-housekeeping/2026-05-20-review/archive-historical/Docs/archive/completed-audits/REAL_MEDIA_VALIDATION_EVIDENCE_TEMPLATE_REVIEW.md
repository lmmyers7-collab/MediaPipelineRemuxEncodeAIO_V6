# Real-Media Validation Evidence Template Review

Date: 2026-05-14  
Last reviewed against template changes: 2026-05-15

Gap analysis of `Docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md` against the V5 validation requirements described in `Docs/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`. Identifies missing evidence fields, incomplete capture sequences, and sections that should be strengthened.

This document does not modify the template. All changes to the template require deliberate operator review because the template is also the worksheet generator's output format.

2026-05-15 status note: the template now includes `WebView Pilot Evidence Packet Capture`, and `New-RealMediaValidationWorksheet.ps1` can prefill sample category plus expected-route columns. That partially resolves the earlier sample-validation-log/evidence-trail gap, but the remaining diagnostics-target and publish-reconciliation guidance gaps still apply.

---

## Template Summary

The current template (`REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`) covers these sections:

1. Validation Run Identity
2. Pre-Run Checklist
3. Sample Batch
4. WebView Pilot Evidence Packet Capture
5. Queue Evidence (Before Launch)
6. Run Evidence (During Processing)
7. FFmpeg / Run Log Evidence
8. Subtitle Evidence
9. Audio Evidence
10. Completed Manifest Evidence
11. Size-Growth Evidence
12. Pending Publish Evidence
13. Plex / Direct Play Observation (Optional)
14. Diagnostics State After Run
15. Overall Decision
16. Follow-Up Items
17. Acceptance Boundary

---

## Gaps Found

### Gap 1 — No Explicit Diagnostics Target Sequence

**Where**: Between "FFmpeg / Run Log Evidence" (Section 6) and "Subtitle Evidence" (Section 7).

**Issue**: The template tells the operator to inspect `last_stderr_log`, but does not provide the sequence of diagnostics targets to check for each evidence type. Operators need to know: for a subtitle failure, start with `last_stderr_log`; for a completed manifest mismatch, start with `completed_manifest` tail.

**Recommendation**: Add a "Diagnostics Investigation Sequence" sidebar or callout after Section 6. Reference `Docs/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md` and `Docs/COMPLETED_PENDING_FAILURE_PLAYBOOK.md` for per-scenario sequences.

**Severity**: Medium — operators familiar with the system know where to look; new operators may skip the right target.

---

### Gap 2 — Route Reason Code Not Captured

**Where**: Section 4 (Queue Evidence) and Section 9 (Completed Manifest Evidence).

**Issue**: Both sections capture `route` (remux/encode) but do not have a field for `route_reason_code` or `route_reason`. The reason code is what distinguishes between encode-by-size, encode-by-profile, encode-by-compatibility-override, etc.

**Recommendation**: Add `Route reason` and `Route reason code` columns to the Queue Evidence and Completed Manifest Evidence tables.

**Severity**: Medium — without reason code, route disagreements are harder to investigate.

---

### Gap 3 — `GET /api/publish-reconciliation` Not Mentioned

**Where**: Section 11 (Pending Publish Evidence).

**Issue**: The publish reconciliation route (`GET /api/publish-reconciliation`) provides a backend-authored cross-reference of Completed rows, Pending Publish rows, and the latest durable drain summary. This is the most reliable way to verify that a completed output has a corresponding pending publish entry. The template does not mention this route.

**Recommendation**: Add a row to Section 11: "Publish reconciliation check (GET /api/publish-reconciliation): pass / fail / not applicable."

**Severity**: Medium — operators doing deferred-publish validation may miss this cross-reference.

---

### Gap 4 — Sample Validation Log Not Included as Evidence Trail

**2026-05-15 status**: Partially addressed. The template now has a `WebView Pilot Evidence Packet Capture` section and the worksheet helper can generate matching rows. A future template pass should still add an explicit "append evidence note" row in Overall Decision if the operator wants the worksheet to drive the final JSONL note step.

**Where**: Section 16 (Acceptance Boundary) and Section 13 (Overall Decision).

**Issue**: The sample validation log (`POST /api/sample-validation/append`) is the formal operator evidence record. The template does not include a step for appending a validation record after evidence collection is complete. The Acceptance Boundary section states that evidence "does not automatically accept" but does not tell operators to append a validation record.

**Recommendation**: Add a step to the Overall Decision section: "Append sample validation record via WebView Home → Validation Log. Include `proof_strength`, `operator_decision`, and a note linking to this worksheet."

**Severity**: Low — the template is still useful without this step, but the sample validation flow is disconnected from the evidence collection process.

---

### Gap 5 — AudioMaxChannels Verification Not Explicit

**Where**: Section 8 (Audio Evidence).

**Issue**: The Audio Evidence table captures "channel count in output" but does not explicitly check it against `AudioMaxChannels` in Settings. An operator might record "6 channels" without checking whether that exceeds `AudioMaxChannels=2`.

**Recommendation**: Add a column: "Within AudioMaxChannels limit?" to the Audio Evidence table.

**Severity**: Low — most operators will notice a 6-channel-to-2-channel downmix in practice, but the explicit check prevents silent gaps in documentation.

---

### Gap 6 — `last_stdout_log` Not Captured

**Where**: Section 6 (FFmpeg / Run Log Evidence).

**Issue**: The template only mentions stderr log evidence. The stdout log (`last_stdout_log`) contains pipeline sequencing, heartbeat, and signal-handling evidence that is valuable when the stderr shows no errors but the pipeline did not complete normally.

**Recommendation**: Add a row to Section 6: "stdout log reviewed? (last_stdout_log tail) — Y/N — excerpt if relevant."

**Severity**: Low — stderr is the primary target; stdout is a secondary check.

---

### Gap 7 — Network Destination Evidence Section Missing

**Where**: After Section 11 (Pending Publish Evidence).

**Issue**: The playbook lists "Network output destination" as a sample category for coordinator/worker mode. The template has no section for network-mode-specific evidence (worker assignment, Robocopy transfer, cluster log review). The Pending Publish Evidence section partly covers this, but not the coordinator/worker handoff.

**Recommendation**: Add an optional Section 11b: "Network Mode Evidence (if NetworkRole=coordinator or worker)." Fields: worker assigned, `cluster_log` reviewed, transfer confirmed, sidecar written at destination.

**Severity**: Low for standalone mode; Medium for operators running in coordinator/worker mode.

---

### Gap 8 — Worksheet Generator's Smoke List Is Incomplete

**Where**: `New-RealMediaValidationWorksheet.ps1` (copyable commands appended to worksheet).

**Issue**: The worksheet generator appends a list of smoke wrappers to run. This list does not include the newer wrappers added in V5:
- `Test-WebViewScheduleSmoke.ps1` (non-browser)
- `Test-WebViewBrowserScheduleSmoke.ps1` (browser-backed)
- `Test-WebViewRealMediaEvidenceSmoke.ps1` (non-browser)

**Recommendation**: Update the worksheet generator's copyable command list to include all 18 current wrappers. The authoritative list is in `Docs/WEBVIEW_SMOKE_TEST_CATALOG.md`.

**Severity**: Low — the missing smokes are not required for a real-media validation run, but an operator following the worksheet may miss running them.

---

### Gap 9 — Plex Observation Is Optional But Should Be Required for Full Evidence

**Where**: Section 12 (Plex / Direct Play Observation — marked Optional).

**Issue**: The playbook states that Plex/Direct Play observation is a key validation goal for the primary operator use case. Marking it optional allows operators to skip it even when the configuration targets Plex direct play.

**Recommendation**: Change Section 12 from "Optional" to "Required if RoutingProfile targets Plex direct play or direct stream." Add a conditional note: "Skip only if Plex is not the playback target for these samples."

**Severity**: Low — operators using Plex will typically run this check; the optional label just makes it skippable.

---

## Strengths of the Current Template

| Strength | Notes |
|---|---|
| Covers all six playbook evidence categories | Route, audio, subtitle, size, pending publish, and diagnostics state are all present |
| Acceptance Boundary section is explicit | Correctly states what evidence does NOT do |
| Pre-Run Checklist matches playbook | All 6 pre-run checks from the playbook are included |
| Sample Batch table is flexible | Supports any sample count with extensible rows |
| Follow-Up Items section | Ensures issues discovered during validation are tracked |
| `See Also` references are accurate | Points to playbook, validation record flow, artifact paths, and failure triage |

---

## Prioritized Improvement Summary

| Gap | Priority | Effort | Notes |
|---|---|---|---|
| Gap 2: Route reason code missing | Medium | Low (add columns) | High diagnostic value |
| Gap 3: Publish reconciliation route missing | Medium | Low (add row) | Improves deferred-publish validation |
| Gap 1: Diagnostics target sequence missing | Medium | Medium (add sidebar) | Helps new operators |
| Gap 4: Sample validation append step missing | Low | Low (add step) | Closes the evidence loop |
| Gap 8: Worksheet generator smoke list incomplete | Low | Low (update script) | Smoke completeness |
| Gap 7: Network mode evidence missing | Low | Medium (add section) | Only relevant for multi-worker mode |
| Gap 5: AudioMaxChannels check not explicit | Low | Low (add column) | Minor audit completeness |
| Gap 6: stdout log not captured | Low | Low (add row) | Secondary diagnostic only |
| Gap 9: Plex section marked optional | Low | Low (update label) | Clarification only |

---

## Freshness Review — 2026-05-15 (CLN2-19)

Checked template against the playbook's description of the two newest proof panels: the Completed-page `Real-Media Output Proof` board and the `GET /api/publish-reconciliation` (Publish Reconciliation) panel.

| Panel | Playbook reference | Previously in template | Action taken |
|---|---|---|---|
| `Real-Media Output Proof` board | Playbook line: "Completed Real-Media Output Proof rows do not disagree across output/sidecar, route/size/media, pending/drain, diagnostics/runtime, Sample Validation handoff, and operator-boundary evidence" | Missing | Added after Completed Manifest Evidence: a proof-ladder capture table and read-only boundary note |
| Publish Reconciliation (`GET /api/publish-reconciliation`) | Playbook: "Pending Publish / Completed" in drain proof row | Missing (Gap 3 from prior review) | Added after Pending Publish Evidence table: a correlation check line with conditional applicability note |

All other prior gaps (Gap 1–2, Gap 4–9) remain open. No additional gap was found. Template wording is consistent with `backend-owned`, `read-only`, and the mutation boundary reminder at the top.

**Files changed**: `Docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md` — two targeted additions.
**Files inspected**: `Docs/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`, `Docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md`.

---

## See Also

- Evidence template: `Docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`
- Validation playbook: `Docs/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`
- Diagnostics target allowlist: `Docs/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md`
- Completed/Pending failure playbook: `Docs/COMPLETED_PENDING_FAILURE_PLAYBOOK.md`
- Log artifact catalog: `Docs/LOG_ARTIFACT_CATALOG.md`
- Smoke test catalog: `Docs/WEBVIEW_SMOKE_TEST_CATALOG.md`
