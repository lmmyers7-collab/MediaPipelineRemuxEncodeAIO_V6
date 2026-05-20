# Runtime Artifact Classification Sort Notes

Date: 2026-05-14

Reviews `Docs\RUNTIME_ARTIFACT_INVENTORY.md` for artifact grouping, safe-action guidance, and sort order. Source: `Docs\RUNTIME_ARTIFACT_INVENTORY.md`.

---

## Summary

`RUNTIME_ARTIFACT_INVENTORY.md` is well-organized. Artifacts are grouped by subsystem owner and lifecycle purpose. Safe-to-delete guidance is present for every entry. No additions or reordering are required. These notes record the current classification for reference.

---

## Current Section Organization

| Section | Artifact types | Correct grouping |
|---|---|---|
| Progress and Queue | Queue snapshot, progress JSON, pipeline events log, run log stdout/stderr, run logs folder | Correct — all pipeline-run evidence |
| Active Jobs | ActiveJobs folder, per-job launch records | Correct — process lifecycle records |
| Completed Manifest | completed_manifest.json | Correct — output evidence |
| Failure State | Failure markers, failure reports, latest failure JSON/report, clear manifest | Correct — error state; clear manifest correctly separated from reports |
| Pending Publish (Parked Outputs) | Pending publish root, per-batch manifests, parked payloads, drain summary | Correct — drain-owned artifacts grouped together |
| Pipeline Control Flags | Pause, stop, rescan flags | Correct — volatile lifecycle flags |
| Audit and Rerun | Audit CSV output, priority CSV, audit reports folder | Correct — reporting artifacts |
| Sample Validation Log | Validation log JSONL | Correct — operator evidence only |
| Command Journal (In-Memory) | In-memory bounded FIFO | Correct — transient; correctly noted as in-memory only |

---

## Safe-To-Delete Guidance (Confirmed Complete)

Every artifact entry includes a "Safe to delete manually" column. Summary of guidance:

| Safe to delete | Artifacts |
|---|---|
| **No** | Queue snapshot, progress JSON, pipeline events, stdout/stderr logs during active run; ActiveJobs during active work; completed manifest; failure markers (use Clear command); latest failure JSON during investigation; pending publish manifests and parked payloads; drain summary during ongoing drain; pipeline control flags; command journal (not applicable — in-memory) |
| **Yes (after reviewing)** | Failure reports, audit CSV output, priority CSV, audit reports folder, old run logs |
| **Yes (operator evidence only)** | Sample validation log |
| **No / use app command** | Failure markers: must use "Clear Failure Errors" command, not direct delete |

This guidance is correct and complete. No new safe-delete policies are needed.

---

## Artifact Groups For Operator Reference

The following grouping maps well to the inspection sequences operators commonly need:

| Operator investigation | Relevant sections |
|---|---|
| "Why did this job fail?" | Failure State, Progress and Queue (stderr log) |
| "What did the pipeline last do?" | Progress and Queue (events log, stdout log) |
| "Is a job currently running?" | Active Jobs |
| "What outputs were completed?" | Completed Manifest |
| "What is parked for publishing?" | Pending Publish |
| "What did the last audit find?" | Audit and Rerun |
| "What command was last issued?" | Command Journal (via `/api/commands` route) |

---

## Potential Enhancement (Not Implemented)

The "Command Journal" section notes the artifact is in-memory and resets on backend restart. A brief note clarifying that the journal is also accessible via `GET /api/commands` (and rendered in WebView Command History) would complete the reference. This is a minor doc enhancement; the existing note is not incorrect.

---

## Files Inspected

- `Docs\RUNTIME_ARTIFACT_INVENTORY.md`: full inventory; all 9 sections read

---

## Task Output

```
Task ID: CLN-022
Files inspected: Docs\RUNTIME_ARTIFACT_INVENTORY.md
Files changed: Docs\RUNTIME_ARTIFACT_SORTING_NOTES.md (created)
Validation: Read all sections; verified safe-to-delete guidance is present for every entry.
Findings: Inventory is correctly organized by subsystem. All 9 sections are logically grouped. No reordering needed.
Open questions: None.
Risk: Low — documentation only.
```
