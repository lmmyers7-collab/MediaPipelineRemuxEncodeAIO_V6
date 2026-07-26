---
file: src/mediapipeline/core/config/recovery.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-07-02
last_reviewed: 2026-06-04
sha256: 61500031f57a225a77fd783948d8f77318f1d4e2209df0ce2fdd06832e71504d
---
# `src/mediapipeline/core/config/recovery.py`

**Purpose:** Startup recovery for the live operator config (config hardening #1). The live config (``MediaPipeline_config.psd1``) is a gitignored operator file. Historically a missing canonical file silently fell back to the legacy ``_chatgpt`` name or to defaults, which surfaced only as a cryptic ``settings loaded=no`` at launch time. This module makes startup self-heal: - canonical present -> ``present`` - canonical missing, legacy here -> copy legacy -> canonical (``migrated``) - local config present/migrated -> seed missing per-user packaged fallback - local config missing, per-user -> use/migrate per-user config - both missing, a backup exists -> ``backup_available`` (names newest; no silent auto-restore) - nothing -> ``absent`` Filesystem only: no PowerShell, no psd1 parsing here, so it stays cheap and unit-testable. Parsing/validation remains the caller's existing path.

**Public symbols:** `ConfigRecoveryResult`, `ensure_canonical_config`, `restore_verified_last_good_config`, `seed_user_config`
**In-repo imports:** `mediapipeline.core.config.identity`, `mediapipeline.core.kernel.config_locations`
**State/config identifiers:** `MediaPipeline_config.psd1`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/config/recovery.py`._
