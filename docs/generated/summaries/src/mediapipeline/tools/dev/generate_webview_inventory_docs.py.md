---
file: src/mediapipeline/tools/dev/generate_webview_inventory_docs.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-20
last_reviewed: 2026-07-20
sha256: 767f77cb6dd91511b47d2a167c8b2d1c1e5d53c23efdf767dbf349540aebb63c
---
# `src/mediapipeline/tools/dev/generate_webview_inventory_docs.py`

**Purpose:** Generate and check the authoritative WebView DOM/global-export inventories. The main WebView document is backend-rendered from ``index.html`` and its partials. Standalone HTML documents under the static tree are auxiliary surfaces. The export inventory follows the scripts referenced by those surfaces and scans the complete recursive ``assets/**/*.js`` tree.

**Public symbols:** `collect_script_exports`, `discover_frontend_surfaces`, `FrontendSurface`, `main`, `render_dom_inventory`, `render_global_export_inventory`, `render_inventories`, `ScriptExports`, `scripts_by_surface`
**In-repo imports:** `mediapipeline.desktop.api.static_files`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/generate_webview_inventory_docs.py`._
