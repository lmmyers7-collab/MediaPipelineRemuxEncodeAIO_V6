# 30-Day Reliability Soak Test Design

Purpose: validate unattended long-run behavior with isolated media roots, injected failure modes, and read-only health evidence. This soak must not run against production source, scratch, output, final-library, or pending-publish roots.

## Isolated Profile

Create a dedicated configuration profile with these roots under a disposable test directory:

| Root | Requirement |
|---|---|
| Source movies / TV | Seeded fixture copies only; record SHA-256 checksums before launch |
| Scratch / Outsource | Dedicated empty directory |
| Encoded output | Dedicated empty directory |
| Final library | Dedicated empty directory |
| LocalBase | Dedicated empty directory with fresh `State\` |
| Pending publish | Under the soak `LocalBase\State\PendingServerPush` only |

Use conservative long-run thresholds unless the test explicitly overrides them:

| Key | Soak value |
|---|---|
| `ConsecutiveRoundFailureBlockLimit` | `12` |
| `ConsecutiveRoundFailureProbeBackoffSeconds` | `900` |
| `PendingPublishBacklogBlockThreshold` | `100` |
| `PendingPublishDeferredBlockThreshold` | `25` |
| `PendingPublishDrainMode` | `manual` for baseline; repeat deferred-drain phase with explicit `trusted` |
| `PendingPublishDrainBatchSize` | `100` |
| `AllowSubtitleHelperFallback` | `false`; repeat degraded-helper phase with explicit `true` |
| `PauseFlagReviewSeconds` | `1800` |
| `PauseFlagBlockSeconds` | `21600` |
| `LocalWorkerHeartbeatGraceSeconds` | `900` |
| `QueueExecutionMaxRunnablePerRound` | `500` |
| `StateDbMaintenanceIntervalSeconds` | `21600` |
| `StateDbWalReviewBytes` | `33554432` |
| `StateDbCompletedJobsMaxRows` | `250000` |
| `PipelineDebugLogMaxBytes` | `104857600` |

## Fault Injection Matrix

| Injection | Expected behavior |
|---|---|
| Hung FFmpeg or helper process | Worker/process watchdog reports blocked or stale evidence; no orphan tool process remains older than stage timeout plus grace |
| Malformed `ffprobe` output | Item fails with evidence; queue continues when failures are transient |
| Locked source/output/pending files | Source remains unchanged; publish parks or retries through backend-owned safety paths |
| Network share outage and recovery | Pending publish grows only to configured backpressure thresholds; safe retry resumes after recovery |
| Deferred publish destination outage with `PendingPublishDrainMode=manual` | Manifests remain parked; no unattended drain is attempted |
| Deferred publish destination recovery with `PendingPublishDrainMode=trusted` | Only trusted manifests drain through existing pending-publish transaction paths, bounded by `PendingPublishDrainBatchSize` |
| Coordinator heartbeat POST partition | Worker aborts local encode before coordinator lease expiry, saves pending done evidence, and does not start a duplicate source claim |
| Coordinator stale reclaim with late terminal report | Reclaimed source remains quarantined until quarantine expiry or accepted late terminal report; late success removes queue eligibility |
| Broken ASS helper startup | With `AllowSubtitleHelperFallback=false`, pipeline exits blocked; with `true`, startup is degraded and health reflects degraded subtitle helper posture |
| Corrupt JSON state artifact | Reader reports recovery/blocker evidence without frontend mutation or silent policy fallback |
| Stale pause flag | Health reports review/blocked state; flag is not auto-cleared |
| Stale or non-terminal ActiveJobs record | Health blocks unattended launch as read-first evidence without unsafe process release or auto-clear |
| Worker child crash | Parent reclaims only the affected slot and preserves claim/result evidence |
| Debug log growth | `pipeline_debug.log` rotates under the existing mutex before exceeding `PipelineDebugLogMaxBytes`; event JSONL rotation behavior is unchanged |
| SQLite WAL and completed-job mirror growth | Opportunistic maintenance runs or reports best-effort failure; completed-job mirror rows trim above `StateDbCompletedJobsMaxRows`; JSONL remains authoritative |
| Autonomy scan over `AUTONOMY_SCAN_LIMIT` | Health reports truncation flags and treats scanned byte totals as lower bounds |

## Acceptance Criteria

- Seed source checksums match after 30 days.
- Pending publish does not grow past configured block thresholds without blocked health evidence.
- Baseline deferred publish does not auto-drain while `PendingPublishDrainMode=manual`.
- Trusted deferred publish drains only trusted manifests through backend-owned validation/transaction paths.
- Network partition tests never process one source concurrently on two workers.
- No FFmpeg, ffprobe, MKVToolNix, OCR, or worker-child process remains older than its stage timeout plus configured grace.
- Continuous mode resumes after transient failures and reports blocked health for persistent failures.
- Memory, handle count, SQLite WAL/SHM size, completed-job SQLite rows, logs, command journals, event files, diagnostics payloads, coordinator failure ledger, reclaimed-source quarantine, and pending done reports stay bounded or expose blocked/review health before unbounded growth.
- Health payload identifies every injected persistent failure using backend-owned evidence; the WebView remains read-only for these policies.

## Minimum Instrumentation

Capture these at least every 15 minutes:

| Signal | Source |
|---|---|
| Runtime reliability counters | `GET /api/snapshot` and Diagnostics autonomy health payload |
| Progress and event tail | `State\Progress\pipeline_progress.json`, `pipeline_events.jsonl` |
| Active jobs and worker slots | `State\ActiveJobs\`, `State\Workers\slot-<n>\` |
| Pending publish backlog | `State\PendingServerPush\*.manifest.json` and drain summary |
| Pending done backlog | `State\App\pending_done_reports\`, `pending_done_reports_review\`, and runtime pending done oldest-age counters |
| Coordinator safety ledgers | `State\App\coordinator_inflight.json` reclaimed-source quarantine, late terminal reports, and failure ledger counts |
| Process list | Windows process snapshot filtered to FFmpeg, ffprobe, MKVToolNix, OCR tools, PowerShell, and Python |
| File handles | Windows handle/process telemetry for scratch, pending publish, and final roots |
| SQLite mirror sizes and row bounds | `State\mediapipeline_state.sqlite3`, `-wal`, `-shm`, completed-job count/max, and `State\state_db_maintenance.json` |
| Debug log size/rotation | `LocalBase\pipeline_debug.log` size, max-bytes setting, and rotation state |
| Autonomy scan completeness | `state_root_scan_truncated`, `local_base_scan_truncated`, and lower-bound byte flags |
| Source checksums | Pre/post checksum manifest for seeded fixture roots |

## Stop Conditions

Stop the soak and preserve evidence if any source checksum changes, an unsafe final-library mutation is detected, a pending-publish manifest is modified outside backend drain/recovery paths, a source is claimed by two workers concurrently, pending done reports or coordinator quarantine grow monotonically for more than one day, process counts grow monotonically for more than one day, or the Local API/API snapshot path stops responding for more than one probe-backoff interval.
