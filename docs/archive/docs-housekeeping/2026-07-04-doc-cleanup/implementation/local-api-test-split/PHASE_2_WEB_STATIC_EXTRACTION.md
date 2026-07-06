# Phase 2: Web Static Extraction

Status: execute after Phase 1 passes

## Purpose

Split `test_local_api_serves_read_only_web_prototype` first. It is the largest
method in the current god-file and mostly verifies WebView/static contracts,
not Local API route behavior.

The end state should be a set of focused Web static modules where failures
identify the affected page or asset bundle.

## Current Problem

`test_local_api_serves_read_only_web_prototype` currently mixes:

- live Local API static serving;
- index bootstrap/cookie assertions;
- asset content-type assertions;
- asset load-order assertions;
- page DOM ID assertions;
- static JavaScript namespace/export assertions;
- queue, completed, pending publish, settings, launch, diagnostics, reports,
  schedule, maintenance, telemetry, progress, contract, rename, cross-page, and
  layout-manager assertions.

This is why a single failure sends the maintainer into thousands of unrelated
assertions.

## Target Files

Create or update these files as needed:

| Target file | Assertions to own |
|---|---|
| `test_application_facade_web_static_shell.py` | index bootstrap, auth-cookie posture, script order, content types, common app shell, command history, common DOM/formatters/API assets. |
| `test_application_facade_web_static_completed.py` | Completed HTML IDs, completed asset bundles, completed review/proof/evidence/diagnostics/open-action assertions. |
| `test_application_facade_web_static_queue.py` | Queue HTML IDs, queue bundle exports, queue review/detail/launch/file-settings/static affordances. |
| `test_application_facade_web_static_pending_publish.py` | Pending Publish HTML IDs and pending recovery/diagnostics/drain/confidence/detail assertions. |
| `test_application_facade_web_static_settings.py` | Settings HTML IDs, settings builders, metadata, patch review, policy-impact, raw triage, safety locks. |
| `test_application_facade_web_static_launch.py` | Launch page, launch readiness/history/risk/scope/real-media/preflight/controller/static control assertions. |
| `test_application_facade_web_static_diagnostics_reports.py` | Diagnostics, diagnostics tail/state summary, reports, schedule, maintenance, telemetry, progress, contract assertions. |
| `test_application_facade_web_static_cross_page.py` | Cross-page context, sample-validation, layout-manager, home/topbar/activity, cross-page target assertions. |

Keep a small Local API static-serving smoke either in
`test_application_facade_local_api_http.py` or in the shell static file. That
smoke should verify that the backend serves the index and representative assets
with the right content type. It should not own every page contract.

## Extraction Strategy

1. Use the assertion-target inventory from prework.
2. Open `ASSERTION_MIGRATION_LEDGER.md` and create/update rows for each
   assertion category before deleting source assertions.
3. Introduce a served-static fixture that fetches all assets once per test class
   or per helper call, but does not share mutable server state between tests.
4. Move shell/bootstrap/content-type assertions first.
5. Move one page group at a time.
6. After each page group, run that new module plus the original god-file.
7. Only delete the original assertions after the new module passes and the full
   old module still passes.
8. Mark the corresponding ledger rows resolved with the replacement test names
   and validation command.
9. Once all assertions are moved, replace the original giant method with either:
   - a small Local API static-serving smoke; or
   - no test, if the smoke lives in a new target module.

## Recommended Test Method Split

Do not create another 1,000-line test in a different file. Use multiple methods.

Suggested shell methods:

- `test_served_index_uses_http_only_cookie_bootstrap`
- `test_served_static_assets_return_expected_content_types`
- `test_index_references_static_assets_in_dependency_order`
- `test_common_app_shell_exports_are_static_pinned`
- `test_command_history_diagnostics_contract_is_static_pinned`

Suggested page methods:

- `test_completed_page_static_contract`
- `test_completed_evidence_and_proof_assets_are_static_pinned`
- `test_completed_review_and_selection_assets_are_static_pinned`
- `test_queue_page_static_contract`
- `test_queue_file_override_static_contract`
- `test_pending_publish_page_static_contract`
- `test_pending_publish_drain_and_recovery_contracts_are_static_pinned`
- `test_settings_page_static_contract`
- `test_settings_builder_contracts_are_static_pinned`
- `test_launch_page_static_contract`
- `test_launch_preflight_and_control_contracts_are_static_pinned`
- `test_diagnostics_reports_static_contracts`
- `test_cross_page_context_static_contract`

## Migration Guardrails

- Preserve the served-vs-file-read distinction. If an assertion specifically
  proves Local API serves a file with the expected content type, keep it in a
  served-static test.
- Prefer file-read asset bundles for pure static contract assertions. They are
  faster and avoid coupling every page assertion to server startup.
- Keep page-specific assertions with the page-specific test file.
- Use helper readers for asset bundles, but keep assertion intent visible in
  the test method.
- Avoid one umbrella `test_all_web_static_contracts` method.
- Do not move WebView assertions into Local API route-domain modules.

## Phase Validation

Run after each page extraction:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest tests.python.desktop.<target_module> -q
& $py -m unittest tests.python.desktop.test_application_facade_local_api -q
```

Replace `<target_module>` with the module just created or updated, such as
`test_application_facade_web_static_completed`.

Run after the full phase:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade_web_static*.py" -q
& $py -m unittest tests.python.desktop.test_application_facade_local_api -q
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Exit Criteria

- The original 4,836-line method is gone or reduced to a small served-static
  smoke.
- WebView/static assertions are grouped by page or common shell.
- No new test method exceeds a size that makes troubleshooting impractical.
- Running only a failing page module is possible.
- No assertion category from the prework inventory disappeared without a noted
  reason.
- The Phase 2 section of `ASSERTION_MIGRATION_LEDGER.md` has no pending rows
  for the moved Web static assertions.
