---
file: tests/webview/test_webview_navigation_static.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 35ae3a4b1543838001e21353c4be221a8972c480c52637c3d818f95acd2877dc
---
# `tests/webview/test_webview_navigation_static.py`

**Purpose:** Static navigation structure tests for the WebView single-page shell. Parses the Local API rendered index template — no browser, no Node.js, no subprocess. Verifies nav button structure, page panel presence, initial active state, and cross-page navigation target validity. Does not test JavaScript execution, CSS rendering, or runtime page switching.

**Public symbols:** `WebViewNavigationStaticTests`
**In-repo imports:** `mediapipeline.desktop.api.static_files`, `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/webview/test_webview_navigation_static.py`._
