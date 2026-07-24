---
file: tests/python/desktop/test_rename_workbench.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: rename
token_priority: medium
owner_domain: tests
last_modified: 2026-07-23
last_reviewed: 2026-06-04
sha256: bd847bfe835541b386b29f337a2fa0d61a779e3c18b0ca3378e6df2e823b3878
---
# `tests/python/desktop/test_rename_workbench.py`

**Purpose:** Rename Workbench static + backend tests. Asserts the standalone-tool redesign: - header stepper removed, three workflow sections retained, queue controls removed - staged-path controls use explicit safe labels - single Title/Show field, Movie Title removed - Template labels match the new copy - Confirm + Result dialogs present - Browse Folder JS handler uses folder_files mode - Backend folder_files browse mode returns ok shape

**Public symbols:** `RenameBackendBrowseModeTests`, `RenameBackendPathDialogScriptTests`, `RenameWorkbenchHtmlTests`, `RenameWorkbenchJsTests`
**In-repo imports:** `mediapipeline.tools.paths`
**HTTP routes:** `/api/rename/filter-cases`, `/api/rename/undo`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/python/desktop/test_rename_workbench.py`._
