---
file: src/mediapipeline/core/rename/cleaning_policy.py
pipeline_stage: rename
token_priority: medium
owner_domain: rename
last_modified: 2026-07-12
last_reviewed: 2026-06-04
sha256: 01c3eee5f56a0a92d10b0a37911887aa03de17d515cf299a0c0a481e94e5f0b3
---
# `src/mediapipeline/core/rename/cleaning_policy.py`

**Purpose:** Rename cleaning policy parsing and request enrichment.

**Public functions:** `dict_bool()`, `dict_str()`, `dict_terms()`, `normalize_rename_cleaning_policy()`, `remove_terms_from_request()`, `rename_cleaning_policy_fingerprint()`, `rename_cleaning_policy_from_config()`, `rename_cleaning_policy_from_request()`, `rename_cleaning_policy_from_resolved()`, `rename_request_uses_staged_cleaning_policy()`, `rename_request_with_cleaning_policy()`
**In-repo imports:** `mediapipeline.core.kernel.config_keys`, `mediapipeline.core.rename.constants`, `mediapipeline.core.rename.movie`, `mediapipeline.core.rename.tv`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/rename/cleaning_policy.py`._
