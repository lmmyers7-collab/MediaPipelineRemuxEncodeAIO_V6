# Phase 1: Test Harness And Shared Fixtures

Status: execute after baseline passes

## Purpose

Extract shared test support before moving test ownership. This reduces risk in
later phases because every new module can use the same Local API helpers,
server setup, static asset readers, and namespace-export assertions.

This phase should make small, behavior-preserving edits. It should not split
the giant Web prototype test yet.

## Target Files

Create:

- `tests/python/desktop/application_facade_test_support.py`

Update:

- `tests/python/desktop/test_application_facade.py`
- `tests/python/desktop/test_application_facade_local_api.py`
- `tests/python/desktop/test_application_facade_web_static.py`
- every `tests/python/desktop/*.py` module that imports shared fixtures from
  `tests.python.desktop.test_application_facade`

Do not create empty future test modules in this phase.

## Support Module Responsibilities

The support module may own:

| Helper | Purpose |
|---|---|
| `DummyFacadeService` | Canonical dummy facade service fixture currently provided by `test_application_facade.py`. |
| `DummyWorkflowFacadeService` | Canonical workflow-capable dummy facade service fixture currently provided by `test_application_facade.py`. |
| `DummyProc` | Canonical dummy process fixture currently provided by `test_application_facade.py`. |
| `_resolved(...)` | Canonical resolved-path fixture helper currently provided by `test_application_facade.py`. |
| `_render_static_index_html(...)` | Canonical static-index render helper currently provided by `test_application_facade.py`. |
| `LocalApiHttpTestMixin` | `_get_json`, `_post_json`, `_options`, `_get_raw` helpers used by Local API tests. |
| `served_webview_fixture(...)` | Starts `LocalApiServer` with `DummyFacadeService`, fetches index/assets, and stops the server reliably. |
| `read_static_asset_bundle(...)` helpers | File-read based static asset bundle readers used by WebView static tests. |
| `assert_namespace_export(...)` | Shared namespace export regex assertion. |
| `COMMAND_HISTORY_ASSET_ORDER` | Shared command-history asset order list. |
| small dataclass fixtures | Optional typed bundle objects if they make assertions clearer. |

The support module must not:

- start a server at import time;
- write to source/media paths;
- import browser automation;
- hide route mutation assertions behind broad helpers;
- create a second source of truth for route inventories;
- leave active test modules importing shared fixtures from
  `test_application_facade.py` after this phase, except for explicitly
  documented temporary leftovers found by the import scan below;
- depend on current working directory beyond the existing repo-root helper.

## Step Plan

1. Move `DummyFacadeService`, `DummyWorkflowFacadeService`, `DummyProc`,
   `_resolved`, and `_render_static_index_html` from
   `test_application_facade.py` to `application_facade_test_support.py`.
2. Update every active test importer to import those fixtures from
   `application_facade_test_support.py`.
3. Run this import scan and resolve every real import hit:

   ```powershell
   rg "from tests\.python\.desktop\.test_application_facade import" tests\python\desktop
   ```

   A quoted historical string inside a legacy-removal test can remain only if
   the test intentionally checks old import text.
4. Move `_assert_namespace_export` to
   `application_facade_test_support.py` as `assert_namespace_export`.
5. Move `COMMAND_HISTORY_ASSET_ORDER` to the support module.
6. Move `_get_json`, `_post_json`, `_options`, and `_get_raw` into
   `LocalApiHttpTestMixin`.
7. Update `LocalApiServerTests` to inherit the mixin.
8. Move the WebView static asset bundle readers from
   `test_application_facade_web_static.py` to the support module only if doing
   so does not obscure failure messages.
9. Keep existing test names and locations unchanged.
10. Leave `test_application_facade.py` with no owned fixtures. Delete it in
    Phase 5 if no active import or documented compatibility need remains.
11. Run the phase validation before moving any test methods.

## Expected Result

After this phase, the old large files still own the same tests, but duplicate
helper code is reduced, `application_facade_test_support.py` is the canonical
fixture provider, and every later test module can import stable support without
depending on a `test_*.py` fixture module.

## Phase Validation

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest tests.python.desktop.test_application_facade_local_api -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
@'
import ast
from pathlib import Path

offenders = []
for path in Path("tests/python/desktop").glob("test*.py"):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "tests.python.desktop.test_application_facade":
            offenders.append(f"{path}:{node.lineno}")
if offenders:
    raise SystemExit("Remaining fixture imports from test_application_facade.py:\n" + "\n".join(offenders))
print("No active fixture imports from test_application_facade.py remain.")
'@ | & $py -
```

If this phase fails, rollback is straightforward: restore the moved helpers to
the original files and delete `application_facade_test_support.py`.

## Review Checklist

- Test count is unchanged.
- No assertions moved yet.
- Shared dummy fixtures no longer live in `test_application_facade.py`.
- Active test imports use `application_facade_test_support.py`.
- Helper names are explicit and failure messages still point to the failing
  contract.
- No duplicate tests appear in discovery.
- No product source files changed.
