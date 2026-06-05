# Terminology Consistency Guide

Date: 2026-06-02

Defines preferred vocabulary for MediaPipelineRemuxEncodeAIO documentation, WebView operator-facing copy, and API contract descriptions. Use this guide when writing or reviewing docs to prevent vocabulary drift.

---

## Core Term Definitions

### Launch Scope

**Preferred**: "backend launch scope"

The set of files the backend pipeline processes when started. This is determined by the backend's own state (queue snapshot, priority markers, source paths) — not by what the WebView table currently displays.

**Avoid**:
- "filter scope" when referring to launch behavior
- "visible rows" as a proxy for what gets processed
- "selected rows" to mean the pipeline will only process those rows

**Correct usage**: "The backend launch scope is not narrowed to the visible WebView table subset."

**Incorrect usage**: "The pipeline will process the filtered rows."

---

### Display Filters

**Preferred**: "display filters" or "table filters"

The text/status/investigation filters in Queue, Completed, and Pending Publish tables that control which rows are visible in the WebView. They do not affect backend launch scope, recovery plan scope, or drain scope.

**Avoid**:
- "active filters" without clarifying that they are display-only
- "scope filters" (implies they narrow backend scope — they do not)
- "query filters"

**Correct usage**: "Active display filters do not change backend launch, rerun, drain, or publish scope."

**Incorrect usage**: "Apply a filter to narrow the pipeline's scope."

---

### Backend-Owned

**Preferred**: "backend-owned"

Describes logic, data, or decisions that the backend controls exclusively. The frontend cannot replicate, bypass, or substitute for backend-owned behavior.

**Avoid**:
- "backend-computed" (acceptable but less precise)
- "server-side" (not wrong, but the Local API is localhost — "backend" is clearer)
- "backend-controlled" (acceptable alternative)

**Correct usage**: "The rename plan is backend-owned — the backend rebuilds it from state, not from the frontend-submitted table."

---

### Read-Only

**Preferred**: "read-only" (hyphenated as adjective)

Describes a panel, field, route, or operation that returns information without making any change.

**Avoid**:
- "view-only" (not an established term in this codebase)
- "observation-only" (acceptable in a few specific contexts but not universal)
- "informational" without clarifying that no mutation occurs

**Correct usage**: "The Network page is read-only — it shows coordinator/worker state but does not start, stop, or reconfigure workers."

---

### Acceptance

**Preferred**: "accepted" or "marked accepted" — used only in the sample validation context.

Describes a formal operator record in `sample_validation_log.jsonl` that a media sample has been validated. Acceptance is evidence-only: it does not trigger processing, clear failures, drain pending publish, or alter manifests.

**Avoid**:
- Using "acceptance" to mean that a completed job was verified as correct (use "verified" or "proof reviewed")
- Using "accepted" to mean the backend approved a rename plan (use "confirmed" or "applied")

**Correct usage**: "The sample validation record flow lets operators append an evidence note. It does not mark the sample as accepted in any automated sense."

---

### Proof vs. Evidence

**Preferred**: "evidence" for accumulated operator records and log data. "Proof" is acceptable when referring to a specific comparison panel (e.g., "Real-Media Output Proof ladder") but should not be used loosely.

**Avoid**:
- "proof" as a synonym for "confirmation" or "approval"
- "evidence" as a synonym for a test pass (smokes produce "assertions," not "evidence")

**Correct usage**: "Collect evidence from the Diagnostics tail, Completed manifest, and Pending Publish panel before trusting a real-media run."

**Incorrect usage**: "The smoke test proves that the pipeline processed media correctly." (Smokes do not process real media.)

---

### Drain

**Preferred**: "drain" for the operation of moving parked outputs from `State/PendingServerPush` to their destination.

**Avoid**:
- "publish" used alone when the action specifically drains the pending queue (use "Publish Parked Outputs" — the full operator term)
- "send" as a synonym for drain

**Correct usage**: "Use **Publish Parked Outputs** to drain the pending queue after confirming the destination is writable."

**Incorrect usage**: "Click Publish to send your completed files."

---

### Parked / Pending

**Preferred**: "parked" for outputs that have been deferred due to destination unavailability or operator choice. "Pending" refers to the manifest state (`pending_move`, `parked`, `parked_recovered`, etc.).

**Avoid**:
- "stuck" (implies a bug — parked is intentional)
- "queued for publish" (the pipeline queue is separate)

**Correct usage**: "Parked outputs remain in `State/PendingServerPush` until drained. Check manifest state and destination readiness before draining."

---

### Guardrail

**Preferred**: "mutation guardrail" for frontend checks that block premature high-risk actions (Apply Readiness, Publish Button Guard, Save-Readiness).

**Avoid**:
- "guard" alone (too generic; clarify it is a mutation guard)
- "lock" (implies a backend lock — backend has launch-lock; frontend has guardrails)
- "safety net" (informal)

**Correct usage**: "Mutation guardrail: this checklist cannot retry, launch, drain, save, rename, repair, delete, publish, open arbitrary paths, or bypass backend validation."

---

### Mutation

**Preferred**: "mutation" for any state change: config write, file rename, process launch, flag write, or log append.

**Avoid**:
- "action" when the context is about whether something changes state (use "mutation" to be precise)
- "destructive" for all mutations (reserve "destructive" for irreversible mutations like rename/apply without undo manifest)

---

### Sidecar

**Preferred**: "sidecar" for the `.mediapipeline.json` metadata file that accompanies a completed output or rename target.

**Avoid**:
- "manifest" for sidecar files (manifests are `completed_jobs.jsonl`, `pending_push_manifest.jsonl`, etc. — separate files)
- "metadata file" (acceptable but imprecise)

---

### Manifest

**Preferred**: "manifest" for:
- `completed_jobs.jsonl` → "Completed Manifest" or "Completed Jobs Manifest"
- `pending_push_manifest.jsonl` → "Pending Publish Manifest" or "Pending Manifest"

**Avoid**:
- "manifest" for sidecar files (sidecars are separate)
- "record" as a synonym for manifest (a manifest is a collection of records)

---

### Scratch

**Preferred**: "scratch" or "scratch folder" for the `Outsource` path — the working area where the pipeline writes in-progress encode output before atomic rename to the output path.

**Avoid**:
- "temp" or "temporary" (the scratch folder is a configured path, not an OS temp dir)
- "working folder" (non-standard in this codebase)

**Correct usage**: "Do not modify, delete, or rename files in the scratch folder during an active encode."

---

### Route / Route Decision

**Preferred**: "route decision" for the backend's choice between remux (copy container) and encode (transcode) for a given file.

**Avoid**:
- "processing mode" (ambiguous)
- "encoding choice" (too narrow — remux is also a route)

**Correct usage**: "The route decision (remux or encode) is stored in the completed manifest and the output sidecar."

---

## Vocabulary Table

| Preferred term | Acceptable alternatives | Avoid |
|---|---|---|
| Backend-owned | backend-controlled, backend-authored | server-side, frontend-inaccessible |
| Display filters | table filters | scope filters, query filters, active filters (without qualifier) |
| Backend launch scope | backend processing scope | visible rows, filtered rows, selected rows |
| Read-only | — | view-only, passive, informational |
| Drain | Publish Parked Outputs (full button label) | send, push, flush |
| Parked | deferred | stuck, queued for publish |
| Mutation guardrail | guard, Apply Readiness, Publish Button Guard, Save-Readiness | lock, safety net |
| Sidecar | `.mediapipeline.json` file | manifest (when referring to sidecar) |
| Manifest | completed manifest, pending manifest | record, sidecar |
| Scratch | scratch folder, Outsource path | temp, working folder |
| Route decision | route | processing mode, encoding choice |
| Evidence | log data, operator records | proof (unless referring to the specific "proof ladder" panel) |
| Acceptance | (sample validation context only) | completion, approval |
| Browser-backed smoke | browser smoke | Node-based smoke (these are distinct) |
| CDP / Chrome DevTools Protocol | CDP (after first-use spell-out) | DevTools, remote debugging, Puppeteer/Playwright names |
| Active Media Policy Boundary | active policy boundary | "saved settings" alone (too vague) |
| Continuous schedule-stop watcher | schedule-stop watcher | "scheduler", "timer" |
| Publish Reconciliation | reconciliation panel | "completed/pending check", "drain summary" |

---

## Phrases to Standardize

| Nonstandard phrase | Preferred replacement |
|---|---|
| "filter to narrow what the pipeline processes" | "display filters do not change backend launch scope" |
| "the pipeline will process visible rows" | "the pipeline processes all in-scope files regardless of display filter" |
| "approve the result" | "accept the result" (sample validation) or "verify the result" (completed proof) |
| "the test proves the pipeline works" | "the smoke verifies WebView rendering; it does not prove real-media processing" |
| "send parked outputs" | "drain pending publish" or "Publish Parked Outputs" |
| "the manifest file" (for sidecar) | "the sidecar" |
| "locked by the backend" | "gated by the backend launch-lock" |
| "block/unblock the filter" | "clear the display filter" |

---

## Mutation Guardrail Standard Wording

The following phrase is used verbatim in the WebView (as identified in `commandHistory.js` and related modules). Use it as-is in operator-facing documentation:

> "Mutation guardrail: this checklist cannot retry, launch, drain, save, rename, repair, delete, publish, open arbitrary paths, or bypass backend validation."

Do not paraphrase or shorten this phrase in operator-facing copy.

---

## See Also

- Operator glossary: `docs/operator/OPERATOR_GLOSSARY.md`
- API evidence/mutation matrix: `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`
- Historical WebView operator copy audit: `docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/admin-audits/WEBVIEW_OPERATOR_COPY_AUDIT.md`
- Historical mutation boundary review: `docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/completed-audits/WEBVIEW_APIPOST_MUTATION_REVIEW.md`

