---
file: src/mediapipeline/contracts/run_monitor.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-07-17
last_reviewed: 2026-07-16
sha256: 4944fb3eab11de10ea62fddc5485e608066a7ae23a08dc1f0badc8a1a758ac6b
---
# `src/mediapipeline/contracts/run_monitor.py`

**Purpose:** Versioned, backend-authored evidence for one accepted Run Once workload. The persisted contract is intentionally strict. It is the correlation boundary between the accepted Backend Queue plan, PowerShell runtime evidence, and terminal artifacts. Display projections may suppress stale claims, but they must never reconstruct missing membership, stages, routes, or track decisions from legacy progress or filename text.

**Public symbols:** `AcceptedQueueIdentity`, `AudioEvidence`, `AudioTrackEvidence`, `CurrentWorkerEvidence`, `EvidenceRecord`, `FailureEvidence`, `OutputEvidence`, `ProgressEvidence`, `RecoveryEvidence`, `RouteEvidence`, `RouteEvidenceSet`, `RunMonitorItem`, `RunMonitorModel`, `RunMonitorPointer`, `RunMonitorRecord`, `RunOutcomeEvidence`, `RunScopedCounts`, `RunSummaryEvidence`, `SidecarEvidence`, `SourceIdentity`, `StageEvidence`, `StopAfterCurrentEvidence`, `SubtitleEvidence`, `SubtitleTrackEvidence`, `TerminalReference`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/contracts/run_monitor.py`._
