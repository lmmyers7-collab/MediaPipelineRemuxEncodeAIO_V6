"""Canonical pipeline contracts.

This package is the single source of truth for:

- Pipeline stage I/O shapes (`stages.py`).
- Configuration shape (`config.py`).
- Cross-stage data shapes (jobs, manifests, events) — added in later phases.

Today these models are stdlib `dataclass` skeletons. ADR-0004 will convert
them to `pydantic` so JSON Schema generation and runtime validation are
automatic. Until then, the models declare intent and field names; do not
rely on runtime validation from these classes.
"""
