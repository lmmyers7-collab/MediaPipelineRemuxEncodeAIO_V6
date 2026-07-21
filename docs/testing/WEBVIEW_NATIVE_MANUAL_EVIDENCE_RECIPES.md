# WebView/Tauri Native Manual Evidence Recipes

These recipes close only genuine Windows/Tauri outcomes that browser automation
cannot prove. A passing browser route assertion is not a passing native outcome.
Keep the associated ledger row `manual_native_only` until the recipe is actually
executed and its artifact is linked from the audit validation ledger.

All recipes must use a newly generated temporary directory. Never select or open
personal configuration, source media, scratch, pending-publish, final-library,
or operator evidence paths.

## `NATIVE-PICKER-ISOLATION-001` — Windows path picker

- **Owner:** Tauri/native QA.
- **Prerequisites:** supported Windows host, current packaged or preview Tauri
  shell, WebView2 runtime, backend started with a temporary LocalBase/config,
  and a temporary folder containing one harmless generated text file.
- **Action:** activate the exact picker control from the ledger; select only the
  generated temporary folder/file; cancel and fail the recipe if the dialog
  initially exposes or resolves to a protected/live operator root.
- **Observable success:** the native dialog opens once, the selected canonical
  path is inside the generated root, the WebView renders that same path, and no
  unrelated field or backend state changes.
- **Failure capture:** screenshot the dialog/result, export the backend request
  and response, record the selected canonical path and Tauri/WebView2 versions,
  and attach relevant console/native logs. Redact user-profile path segments.
- **Cleanup:** close the dialog and shell, verify no owned process remains, then
  delete only the generated temporary directory.

## `NATIVE-OS-SHELL-OPEN-001` — shell file/folder open

- **Owner:** Windows integration QA.
- **Prerequisites:** supported Windows host, a generated temporary folder and
  harmless text file, and the exact backend response identifying that target.
- **Action:** activate one ledger-linked Open File/Open Folder control. Do not
  substitute a personal, media, scratch, pending-publish, or library target.
- **Observable success:** Explorer or the registered harmless-file application
  opens exactly once at the generated target; the WebView remains responsive
  and reports the backend result without an uncaught console/network error.
- **Failure capture:** screenshot the opened target or error dialog, capture the
  backend response, console/network/native logs, process list, and Windows
  application association used for the text file.
- **Cleanup:** close only the launched window/application and remove only the
  generated temporary target after verifying owned processes exited.

## `TAURI-PIPELINE-LOG-UIA-001` — secondary WebView UI Automation

- **Owner:** Tauri accessibility QA.
- **Prerequisites:** supported Windows host with WebView2, current Tauri shell,
  Windows UI Automation probe, and a temporary backend that can open Pipeline
  Log without real media work.
- **Action:** open Pipeline Log from the main shell and inspect the secondary
  `WRY_WEBVIEW` UIA tree without clicking process or media controls.
- **Observable success:** the refresh, mode, and follow controls are individually
  discoverable with stable accessible names/roles and can receive focus; the
  secondary window remains independent of the main navigation surface.
- **Failure capture:** save the complete UIA tree, screenshots of both windows,
  WebView2/Tauri versions, native probe output, and browser accessibility evidence.
- **Cleanup:** close the Pipeline Log and main shell and verify both backend and
  WebView processes terminate.

## `TAURI-PIPELINE-LOG-CLOSE-001` — independent secondary close

- **Owner:** Tauri lifecycle QA.
- **Prerequisites:** the same isolated Windows/Tauri setup as
  `TAURI-PIPELINE-LOG-UIA-001`, with the main and Pipeline Log windows visible.
- **Action:** close only Pipeline Log through its native close affordance.
- **Observable success:** the secondary window disappears, the main shell stays
  responsive, backend ownership/readiness remains correct, and Pipeline Log can
  be opened again exactly once.
- **Failure capture:** timestamped window enumeration before/after, screenshots,
  native logs, backend lifecycle output, and any close/readiness error.
- **Cleanup:** close the main shell through the supported path and verify exact
  process cleanup.

Genuine shell crashes, external-application success semantics beyond the
harmless generated target, playback-device checks, file-association changes,
and OS permission dialogs require their own named native recipe and execution.
They must not be inferred from these recipes or counted as browser passes.
