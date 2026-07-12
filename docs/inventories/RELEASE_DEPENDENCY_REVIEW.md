# Release Dependency Review

This is the release-readiness record for dependency advisories that cannot be
resolved safely by a lockfile override. It complements package acceptance; it
does not replace it.

## Tauri/Wry GTK/glib chain

| Field | Current record |
|---|---|
| Review evidence date | 2026-07-11 |
| Advisory scope | `GHSA-wrw7-89jp-8q8g` / `RUSTSEC-2024-0429`: unsound `glib::VariantStrIter` iterator implementations; affected `glib >=0.15,<0.20`, patched in `0.20.0` |
| Affected distribution targets | Linux GTK/WebKit builds; not reachable by the Windows-only portable ZIP runtime path |
| Locked chain | `tauri 2.11.1` -> `tauri-runtime-wry 2.11.1` -> `wry 0.55.1` -> `gtk 0.18.2` -> `glib 0.18.5` |
| Normal upgrade attempt | An isolated `cargo update` resolved `tauri 2.11.5` and `tauri-runtime-wry 2.11.4`, but retained `wry 0.55.1`, `gtk 0.18.2`, and `glib 0.18.5`; no repository lockfile change was retained because it does not resolve the alert |
| Current upstream constraints | Tauri 2.11.5 and tauri-runtime-wry 2.11.4 require GTK `0.18`; tauri-runtime-wry requires Wry `0.55.0` and current Wry 0.55.1 requires GTK `0.18`; current upstream `dev` manifests retain those constraints |
| Direct-use assessment | The application does not directly depend on glib. Static source scans found no `VariantStrIter` references in Tauri 2.11.5, tauri-runtime-wry 2.11.4, Wry 0.55.1, or GTK 0.18.2. This is reduced observed exposure, not a guarantee that every indirect runtime call is unreachable. |
| Windows package posture | Monitor; do not force a glib override |
| Linux package posture | Block Linux package promotion until a supported upstream chain reaches glib `>=0.20`, or perform a separate explicit Linux risk review and validation before distribution |
| Owner | Release maintainer |
| Review deadline | 2026-08-07 |
| Upgrade trigger | Re-run immediately when Tauri, tauri-runtime-wry, Wry, GTK/WebKit bindings, or the target set changes; the successful trigger is an upstream-compatible graph resolving glib `>=0.20` without local patches/overrides |

Decision framework:

1. Monitor while the advisory is not target-reachable for the Windows release
   lane and the 2026-08-07 deadline has not passed.
2. Upgrade only through a compatible upstream Tauri/Wry release; then run Rust
   checks, the Tauri production-surface audit, copied-bundle package acceptance,
   and clean-machine validation.
3. Validate immediately when the target set expands to Linux or upstream
   identifies a Windows-reachable impact.
4. A Windows-only risk acceptance is allowed only when target reachability,
   owner, expiry, and upgrade trigger are recorded here. It never waives
   package/open/close validation.
5. Do not use `[patch]`, dependency replacement, or a direct glib `>=0.20`
   constraint to mix incompatible GTK-rs generations. The 2026-07-11 supported
   upgrade attempt proves that current upstream releases have not moved the
   chain.

Authoritative sources checked 2026-07-11:

- [GitHub advisory GHSA-wrw7-89jp-8q8g](https://github.com/advisories/GHSA-wrw7-89jp-8q8g)
- [Tauri current `dev` manifest](https://github.com/tauri-apps/tauri/blob/dev/crates/tauri/Cargo.toml)
- [tauri-runtime-wry current `dev` manifest](https://github.com/tauri-apps/tauri/blob/dev/crates/tauri-runtime-wry/Cargo.toml)
- [Wry current `dev` manifest](https://github.com/tauri-apps/wry/blob/dev/Cargo.toml)
- crates.io release metadata resolved by Cargo for `tauri 2.11.5`,
  `tauri-runtime-wry 2.11.4`, `wry 0.55.1`, `gtk 0.18.2`, and `glib 0.18.5`
