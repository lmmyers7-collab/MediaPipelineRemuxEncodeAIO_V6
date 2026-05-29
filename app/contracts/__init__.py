"""Canonical pipeline contracts.

This package is the single source of truth for:

- Pipeline stage I/O shapes (`stages.py`).
- Configuration shape (`config.py`, Pydantic v2).
- Local API command payload shapes (`api_commands.py`).
- File lifecycle/state-machine documentation source (`lifecycle.py`).
- Cross-stage data shapes (jobs, manifests, events) — added in later phases.

`config.py` generates `schemas/config.v1.schema.json`. `stages.py`
generates `schemas/stages.v1.schema.json` and defines the single
Python-to-PowerShell stage execution contract. `lifecycle.py` generates
`Docs/architecture/FILE_LIFECYCLE_MAP.md`.
"""
