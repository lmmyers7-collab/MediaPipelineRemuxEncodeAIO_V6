# app/decide/routing.py

## Current Strain

- Approximate size: 537 lines.
- Risk level: high.
- Mixed concerns: Python-owned pure routing orchestration, route facts,
  stream actions, encoding rules, and output shaping.

## Ideal Split

- Keep existing child modules as the intended boundary:
  `routing_facts.py`, `stream_actions.py`, `encoding_rules.py`, and
  `routing_outputs.py`.
- Move remaining inline orchestration helpers into:
  - `app/decide/routing_trace.py`
  - `app/decide/routing_profiles.py`
  - `app/decide/routing_size_policy.py`
- Keep `routing.py` as the top-level pure decision engine.

## Extraction Order

1. Extract trace/evidence helpers.
2. Extract profile/size helpers if not already covered by existing modules.
3. Keep top-level decision flow intact until parity with PowerShell routing is
   pinned.

## Validation

- `tests/decide/`
- Integration regression matrix.
- PowerShell media route selection checks for parity-sensitive changes.

## Must Not Change

Python/PowerShell routing parity, copy/remux/encode decisions, route evidence,
and mutation-free pure decision behavior.

