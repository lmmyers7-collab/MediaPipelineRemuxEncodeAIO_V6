# Release Dependency Review

This is the release-readiness record for dependency advisories that cannot be
resolved safely by a lockfile override. It complements package acceptance; it
does not replace it.

## Tauri/Wry GTK/glib chain

| Field | Current record |
|---|---|
| Advisory scope | GTK/glib transitive chain reported through Tauri/Wry |
| Affected distribution targets | Linux GTK/WebKit builds; not reachable by the Windows-only portable ZIP runtime path |
| Locked versions | `tauri 2.11.1`, `wry 0.55.1`, `gtk 0.18.2`, `glib 0.18.5` |
| Windows package posture | Monitor; do not force a glib override |
| Owner | Release maintainer |
| Review deadline | 2026-08-07 |
| Upgrade trigger | Upstream compatible Tauri/Wry release that moves the affected chain |

Decision framework:

1. Monitor while the advisory is not target-reachable for the release lane and
   the deadline has not passed.
2. Upgrade only through a compatible upstream Tauri/Wry release; then run Rust
   checks, the Tauri production-surface audit, copied-bundle package acceptance,
   and clean-machine validation.
3. Validate immediately when the target set expands to Linux or upstream
   identifies a Windows-reachable impact.
4. A Windows-only risk acceptance is allowed only when target reachability,
   owner, expiry, and upgrade trigger are recorded here. It never waives
   package/open/close validation.
