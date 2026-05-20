# SmokeTests

This folder contains the project-owned PowerShell smoke wrappers for WebView/Tauri and local API validation.

Run from the repository root:

```powershell
.\SmokeTests\Test-WebViewRowDetailSmoke.ps1
.\SmokeTests\Test-WebViewRenameReadinessSmoke.ps1
.\SmokeTests\Test-LocalApiLifecycleContractSmoke.ps1
.\SmokeTests\Test-WebViewBrowserHighRiskSmoke.ps1
.\SmokeTests\Test-WebViewBrowserLayoutManagerSmoke.ps1
```

Each wrapper resolves the repository root as the parent of this folder, then invokes the matching Python unittest/module. The wrappers are validation entry points only; they must not own media policy, file mutation, settings persistence, queue mutation, pending-publish drain behavior, or browser/frontend business logic.

See `Docs/inventories/SMOKE_TEST_INVENTORY.md` for the full list and safety boundaries.
