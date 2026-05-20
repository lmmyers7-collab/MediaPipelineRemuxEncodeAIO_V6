# MediaPipelineRemuxEncodeAIO V4 Code Cleanup Archive

Status: completed and pruned on 2026-05-06.

This file used to track the V4 cleanup checklist. Completed checklist rows were removed from active tracking after the service split, route/encode policy work, subtitle module extraction, pending-publish hardening, audit module extraction, state-store work, structured diagnostics, and release packaging cleanup were implemented and verified.

## Current State

- `DesktopApp\mediapipeline_desktop_app\services.py` is now a thin facade over focused service mixins.
- PowerShell pipeline logic is split across focused modules for routing, probing, audio, subtitles, queue planning, processing, publish, pending push, audit, config, state, and native tool execution.
- Runtime state is centered under `LocalBase\State`.
- Config save/load, profiles, process launches, queue refresh, CSV rerun, pending publish, failure cleanup, and release packaging have bounded helpers and regression coverage.
- Release builds strip live config, logs, app state, caches, generated backups, and dev-only clutter by default.

## Active Follow-Up

Do not add new completed rows here. Current remaining remediation lives in the active targeted audit checklist in the Codex workspace, not in clean operator packages.
