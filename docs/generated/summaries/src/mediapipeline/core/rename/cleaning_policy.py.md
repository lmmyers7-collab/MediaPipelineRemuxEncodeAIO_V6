---
file: src/mediapipeline/core/rename/cleaning_policy.py
pipeline_stage: rename
token_priority: medium
owner_domain: rename
last_modified: 2026-07-02
last_reviewed: 2026-06-04
sha256: 0591ecfe68162f2d7cf8bfd18d7dd4d1be207ed87323780fe67033d3cb5f2656
---
# `src/mediapipeline/core/rename/cleaning_policy.py`

**Purpose:** Rename cleaning policy parsing and request enrichment.

**Public functions:** `dict_bool()`, `dict_str()`, `dict_terms()`, `remove_terms_from_request()`, `rename_cleaning_policy_from_config()`, `rename_cleaning_policy_from_resolved()`, `rename_request_uses_staged_cleaning_policy()`, `rename_request_with_cleaning_policy()`
**In-repo imports:** `mediapipeline.core.kernel.config_keys`, `mediapipeline.core.rename.constants`, `mediapipeline.core.rename.movie`, `mediapipeline.core.rename.tv`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/rename/cleaning_policy.py`._
