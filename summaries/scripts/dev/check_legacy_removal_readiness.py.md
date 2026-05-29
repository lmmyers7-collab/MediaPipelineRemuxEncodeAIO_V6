---
file: scripts/dev/check_legacy_removal_readiness.py
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-05-29
last_reviewed: 2026-05-28
sha256: 81f490ce911785d8e052d422ac40b611eff70b3cdbe4f1e7c35f5c7defa6f6d4
---
# `scripts/dev/check_legacy_removal_readiness.py`

**Purpose:** Report legacy-surface removal readiness by migration family.

**Classes:** `FamilyStatus`, `LegacyFamily`, `ReferenceMatch`
**Public functions:** `collect_family_statuses()`, `family_files()`, `main()`, `normalize_path()`, `reference_matches()`, `render_report()`, `statuses_to_json()`, `strict_failures()`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths scripts/dev/check_legacy_removal_readiness.py`._
