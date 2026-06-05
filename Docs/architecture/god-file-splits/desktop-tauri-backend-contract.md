# apps/desktop/tauri/src-tauri/src/backend_contract.rs

## Current Strain

- Approximate size: 1,145 lines.
- Risk level: medium.
- Main strain: `validate_backend_web_ui` repeats backend asset fetches and
  required-fragment checks for many WebView scripts in one long function.

## Ideal Split

- `backend_contract/web_ui_assets.rs`: declarative list of asset paths and
  required fragments.
- `backend_contract/web_ui_validator.rs`: shared fetch-and-fragment validation
  helper.
- `backend_contract/bootstrap_validation.rs`: bootstrap placeholder/token leak
  checks.
- Keep `backend_contract.rs` as the public module facade.

## Extraction Order

1. Convert repeated fragment checks into static data structures.
2. Extract one reusable asset validation helper.
3. Move bootstrap/index-specific checks separately.
4. Keep tests near the validator or split test modules only after behavior is
   pinned.

## Validation

- Tauri Rust tests.
- `ops/scripts/dev/start-tauri-preview.bat -CheckOnly`
- Tauri production-surface checks when available.

## Must Not Change

No bearer token leakage, required WebView asset fragments, bootstrap injection,
and backend contract validation failure behavior.

