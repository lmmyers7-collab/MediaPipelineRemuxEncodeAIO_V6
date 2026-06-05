# ops/scripts/smoke

This folder contains the project-owned PowerShell smoke wrappers for WebView/Tauri and local API validation.

Run from the repository root:

```powershell
.\ops/scripts/smoke\Test-WebViewRowDetailSmoke.ps1
.\ops/scripts/smoke\Test-WebViewRenameReadinessSmoke.ps1
.\ops/scripts/smoke\Test-LocalApiLifecycleContractSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserHighRiskSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserLayoutManagerSmoke.ps1
```

Each wrapper resolves the repository root as the parent of this folder, then invokes the matching Python unittest/module. The wrappers are validation entry points only; they must not own media policy, file mutation, settings persistence, queue mutation, pending-publish drain behavior, or browser/frontend business logic.

See `docs/inventories/SMOKE_TEST_INVENTORY.md` for the full list and safety boundaries.
