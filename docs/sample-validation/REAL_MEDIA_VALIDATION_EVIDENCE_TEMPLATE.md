# Real-Media Validation Evidence Template

Copy this template when running a real sample batch through the pipeline to document evidence. Fill in each section before moving to the next. Do not skip sections — incomplete evidence weakens the case for treating the WebView as a daily-driver shell.

This is operator evidence. It does not automatically accept, clear failures, drain pending publish, rewrite manifests, or mark jobs complete. All pipeline decisions remain backend-owned.

For the full validation procedure and sample selection guidance, see `docs/sample-validation/REAL_MEDIA_PILOT_CHECKLIST.md`.

---

## Validation Run Identity

| Field | Value |
|---|---|
| Date / Time | |
| Operator | |
| Machine | |
| Workspace path | |
| Launch surface | ApiAndBrowser / Tauri WebView2 shell |
| Bundled Python version | |
| Bundled PowerShell version | |

---

## Pre-Run Checklist

Complete before starting the pipeline.

| Check | Status | Notes |
|---|---|---|
| External rollback workspace identified if needed | [ ] | |
| WebView backend refresh shows no payload failures | [ ] | |
| Close readiness understood | [ ] | |
| Saved settings posture visible in Settings / Home | [ ] | |
| Queue route evidence visible for at least one row | [ ] | |
| Launch path is backend-owned (not bypassed) | [ ] | |

Do not continue if backend reads fail, close-readiness is unknown during active work, or Settings reports critical errors.

---

## Sample Batch

List the sample files run in this validation. Aim for at least 2-3 different categories from the playbook (H.264 remux-safe, encode-triggering, subtitle-bearing, multi-audio).

| # | Source file | Category | Expected route |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |

---

## WebView Pilot Evidence Packet Capture

Use Home -> Sample Validation -> Preview Record after each sample run. Copy the backend-authored pilot evidence packet status here before appending an evidence note. This packet is guidance only; it does not accept outputs or mutate pipeline state.

| Sample # | Sample label | Packet status | Queue route proof | Completed output/sidecar proof | Diagnostics/run-log proof | Pending Publish posture | Playback/subtitle/audio/size proof | Stop condition hit? |
|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | |
| 2 | | | | | | | | |
| 3 | | | | | | | | |

Packet safe next action:

```
(paste the packet safe-next-action line here)
```

Stop immediately if the packet reports a blocked row, mismatched Queue/Completed proof, missing Diagnostics proof, unexplained Pending Publish state, or playback/subtitle/audio/size disagreement.

---

## Queue Evidence (Before Launch)

For each sample, capture the Queue row evidence before launching.

| Sample # | Route shown | Route reason | Blocked? | Excluded? | Source root |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

Queue snapshot age: _______________

Snapshot still matches expected source files: Yes / No

---

## Run Evidence (During Processing)

| Field | Value |
|---|---|
| ActiveJobs record appeared | Yes / No |
| ActiveJobs PID / log path visible | |
| Progress updates visible while running | Yes / No |
| Close readiness remained unsafe during active work | Yes / No |
| Close readiness returned safe after completion | Yes / No |

---

## FFmpeg / Run Log Evidence

For each sample, capture the run log evidence.

| Sample # | Route reason matches Queue | FFmpeg command visible in log | Last Stderr target | Encode / remux completed without error |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

Last stderr / run log excerpt for reference:

```
(paste relevant lines here)
```

---

## Subtitle Evidence

Fill in only for samples with subtitle tracks.

| Sample # | Subtitle format | Expected action | SRT produced? | TX3G/BDPGS track dropped per config? | ASS/SSA preserved or dropped per config? |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |

Completed manifest subtitle decision field:

```
(paste or describe)
```

---

## Audio Evidence

Fill in only for samples with multi-audio tracks or non-compatible audio.

| Sample # | Audio codecs in source | Expected action (passthrough / transcode / downmix) | Actual action in completed manifest | Channel count in output | Default track language correct? |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |

---

## Completed Manifest Evidence

For each sample, verify the completed manifest entry.

| Sample # | Output path exists | Output path in manifest | Sidecar exists | Route reason in sidecar | Size in manifest |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

Completed manifest file age: _______________

Real-Media Output Proof board (Completed page, selected row): review the proof ladder rows for route/size/media decisions, Pending Publish/drain posture, Diagnostics/runtime signals, and Sample Validation handoff evidence before recording the decision below. This is read-only and does not accept, drain, or mutate state.

| Sample # | Proof ladder status | Route/size/media row | Pending/drain posture row | Diagnostics/runtime row | Sample Validation handoff row |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## Size-Growth Evidence

For each encode sample, document the size relationship.

| Sample # | Source size | Output size | Growth % | Within MaxEncodeGrowthPercent? | SizeGuardMode outcome |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |

---

## Pending Publish Evidence

Fill in only if DeferredPublish is enabled or if a low-space parking event occurred.

| Sample # | Parked? | Pending Publish row visible | Recovery dry-run run? | Do Not Drain rows? | Drain attempted? | Drain summary |
|---|---|---|---|---|---|---|
| 1 | | | | | | |
| 2 | | | | | | |

Publish Reconciliation check (`GET /api/publish-reconciliation` via Completed page → Publish Reconciliation refresh): Completed row / Pending Publish row / drain summary correlated: Yes / No / Not applicable (use when deferred-publish is enabled or any parked output was produced)

---

## Plex / Direct Play Observation (Optional)

| Sample # | Added to Plex | Direct Play confirmed | Transcoding observed | Notes |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |

---

## Policy Proof Pack And Primary Plex Client

Complete this section when the change affects routing, subtitles, audio, Dynamic
HDR, encoders, source/scratch/output movement, or pending publish. The Policy
Proof Pack is a required strict gate for applicable categories; its owned-media
sources remain outside this repository.

| Field | Value |
|---|---|
| Policy Proof Pack run ID | |
| Strict report path | |
| Applicable fixture categories passed | |
| Explicit not-applicable categories and effective-config reason | |
| Primary Plex client label | |
| Primary-client Direct Play/transcode observation | |
| Primary-client HDR indicator observation | |
| Primary-client subtitle/audio/chapter observation | |

---

## Diagnostics State After Run

| Field | Value |
|---|---|
| Failure markers in `State\Failures\Markers\` for these sources | None / List them |
| Diagnostics log shows no errors for these samples | Yes / No / Partial |
| Command history shows successful pipeline/audit start | Yes / No |

---

## Overall Decision

| Field | Value |
|---|---|
| Evidence complete for all samples above? | Yes / No |
| Any Do Not Drain rows in Pending Publish for these samples? | Yes / No |
| Any missing or corrupted outputs? | Yes / No |
| Route decisions match Queue predictions? | Yes / No |
| Audio/subtitle decisions match Settings posture? | Yes / No |
| Operator decision | **Accept as evidence** / **Investigate before accepting** / **Reject** |

---

## Follow-Up Items

| Issue | Action needed | Owner |
|---|---|---|
| | | |

---

## Acceptance Boundary

This evidence documents one sample run. It does not:

- Guarantee all future files will behave the same way.
- Clear failure markers for any source.
- Drain or publish any parked output.
- Accept any job in the completed manifest.
- Replace the need for ongoing monitoring.

A new validation run is warranted after any change to FFmpeg arguments, routing profile, subtitle policy, audio policy, or pending publish behavior.

---

## See Also

- Full validation procedure: `docs/sample-validation/REAL_MEDIA_PILOT_CHECKLIST.md`
- Sample validation record flow: WebView Home → Validation Log
- Runtime artifact paths: `docs/inventories/RUNTIME_ARTIFACT_INVENTORY.md`
- Failure triage: `docs/operator/FAILURE_TRIAGE_WORKSHEET.md`
