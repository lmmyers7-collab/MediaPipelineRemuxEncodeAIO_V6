# 0008. Tauri / WebView2 as the shell

Status: accepted
Date: 2026-05-28

## Context

The desktop shell is Tauri (`DesktopApp/tauri_shell/`) wrapping WebView2
on Windows. The shell launches the bundled Python backend and points
WebView2 at the local API. This is the only shipped shell. Prior plans
considered Electron and a packaged-browser approach; both lost to
Tauri before V6 began.

The decision has been the de-facto architecture for some time but is
not written down. Without an ADR, a future contributor could add an
Electron preview or a "lightweight" alternate shell as a side path,
re-introducing the maintenance load Tauri was chosen to avoid.

`AGENTS.md §9` already notes that "Tauri/WebView2 preview is the
production replacement" is not yet fully true, since PG-3 clean-machine
validation and real-media validation still remain.

## Decision

The shipped desktop shell is **Tauri + WebView2 on Windows**, and the
shipped backend launcher remains the Python local API.

Rules in force:

- **One shell.** No Electron, no packaged-browser, no PWA. If a future
  need arises (e.g. macOS support), it gets its own ADR and explicit
  scope.
- **Tauri owns lifecycle.** Backend start/stop, port choice, ready
  probe, crash recovery. The WebView side never assumes the backend's
  PID; it goes through Tauri's IPC commands or the local API.
- **WebView2 only.** No fallback to Internet Explorer or third-party
  embeddings.
- **Bundle layout.** The Tauri shell, the Python runtime, the PowerShell
  engine, FFmpeg, MKVToolNix, and PgsToSrt all ship inside one
  installer-friendly directory tree. The portable bundle is the
  release artifact.

Open status notes (carried from AGENTS.md):

- PG-3 (clean-machine) validation has not yet certified the shell.
- Real-media validation against the shell launcher remains.

Neither blocks the ADR — both are operational gates for shipping a
release, not architectural decisions.

## Consequences

Code and structure:

- `DesktopApp/tauri_shell/` is the canonical shell location.
- `Pipeline/Tools/` and `Pipeline/PowerShell-*/` are bundled by the
  release packaging script; they do not need ADR-level treatment
  because they are tools, not shell.

Operational surface:

- One install path, one update path. The bundle directory is the unit
  of deployment.
- Single-process model on the user's desktop (Tauri + backend + engine
  subprocesses).

Testing and CI:

- `Test-MediaPipelineRemuxEncodeAIO-Release.ps1` and the SmokeTests
  catalog already cover the shipping shape.
- Clean-machine validation (PG-3) is the release gate.

Migration cost:

- None — this ADR ratifies the de-facto state.

Reversibility:

- Medium. Switching shells would mean rewriting `tauri_shell/`. The
  WebView SPA is shell-agnostic, so the SPA cost would be small.

## Alternatives considered

**Electron.** Heavier runtime, larger bundle, npm dependency surface
that this project actively avoids elsewhere. Rejected.

**Packaged Chromium (CEF).** Equivalent to Electron without the npm
side; still heavier than WebView2 and adds a non-Microsoft dependency
on Windows. Rejected.

**Plain browser pointed at the local API.** Works for development
(see `Start-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.bat`) but is not
a shipping operator experience. The browser does not own backend
lifecycle, breaks shortcuts, and reduces Tauri's offline-bundle value.
Acceptable as a dev mode, not as the shipping shell.

**No shell, CLI only.** ADR-0006 already rules out a parallel
operator surface. Doubly rejected.

## Validation

- The portable bundle continues to ship with `tauri_shell/` and
  `WebView2`-targeting code in the launchers.
- PG-3 clean-machine validation status is tracked in
  `Docs/CURRENT_PROJECT_STATE.md` until the gate clears; the ADR is
  unaffected by that gate.
