# Network Mode Implementation Archive

Status: implementation checklist completed and pruned on 2026-05-06.

Network mode remains an experimental advanced feature, not the default operator path. The original standalone/coordinator/worker implementation checklist has been reduced to this archive because all listed implementation tasks were completed.

## Implemented Scope

- Standalone dispatcher facade over existing queue behavior.
- Coordinator dispatcher with authenticated HTTP claim/done/heartbeat/workers endpoints.
- In-flight job registry with stale-claim reclaim and persisted worker stats.
- Worker dispatcher with polling, heartbeat, crash recovery, single-file pipeline launches, and reclaim abort handling.
- Network settings fields, coordinator token management, worker-mode UI restrictions, coordinator worker board, and worker performance history.
- Optional mDNS coordinator discovery when `zeroconf` is available.
- Worker-specific encode config override JSON.

## Production Readiness Caveat

Standalone mode is the supported default. Coordinator/worker mode still needs broader operational hardening before it should be treated as unattended production infrastructure:

- HTTP body-size caps and clear operator-facing errors.
- More complete integration fixtures for network drops, duplicate done reports, auth failures, worker crash/reclaim loops, and publish-state transitions.
- Longer soak testing with real network shares and mixed GPU/CPU workers.

Those remaining items now live in the active targeted audit checklist.
