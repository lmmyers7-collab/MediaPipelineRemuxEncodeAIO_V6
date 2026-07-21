"""Canonical pipeline contracts.

This package is the single source of truth for:

- Pipeline stage I/O shapes (`stages.py`).
- Source media facts normalized from probe JSON (`source_media.py`).
- Abstract dry-run pipeline plans (`pipeline_plan.py`).
- Verification and publish guard results (`verification.py`).
- Effective decision policy shared by config and decide (`decision_policy.py`).
- Configuration shape (`config.py`, Pydantic v2).
- Local API command payload shapes (`api_commands.py`).
- File lifecycle/state-machine documentation source (`lifecycle.py`).
- Runtime diagnostic evidence (`runtime_evidence.py`).
- Subtitle QA evidence (`subtitles.py`).
- Local API route metadata (`api_routes.py`).
- Backend-owned Run Once monitoring evidence (`run_monitor.py`).
- Cross-stage data shapes (jobs, manifests, events) — added in later phases.

`config.py::Config` is the authority for both the complete
`src/mediapipeline/contracts/schemas/config.v1.schema.json` artifact and the
PowerShell-facing `ops/pipeline/config/schemas/media_pipeline_config.schema.json`
mirror; the latter intentionally omits network-only config fields.
`run_monitor.py::RunMonitorRecord` is the authority for both Run Monitor schema
artifacts, whose only intentional difference is their consumer-specific `$id`.
`stages.py` generates `src/mediapipeline/contracts/schemas/stages.v1.schema.json`
and defines the single Python-to-PowerShell stage execution contract.
`lifecycle.py` generates `docs/architecture/FILE_LIFECYCLE_MAP.md`.
"""
