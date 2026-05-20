# PowerShell Host Wording Audit

Date: 2026-05-14

Checks whether documentation or root scripts incorrectly imply Windows PowerShell 5 is the preferred host for this project. Source: `Docs\POWERSHELL_HOST_EXPECTATIONS.md`, root `*.ps1` wrappers.

This document does not change any wording. It confirms the current state is correct.

---

## Summary

No stale "PS5 is preferred" or "PowerShell 5 is required" wording was found. All inspected files correctly document PS7.6.0 as the bundled and preferred host, with PS5 described as an auto-detected fallback that triggers a re-invocation guard — not a supported daily-use host.

---

## POWERSHELL_HOST_EXPECTATIONS.md Findings

Key phrases confirmed correct:

| Claim | Source text | Assessment |
|---|---|---|
| PS7 required | "PowerShell 7 is required for all scripted operations." | Correct |
| PS5 not supported | "Windows PowerShell 5.1 (the inbox `powershell.exe`) is not a supported host." | Correct |
| Bundled runtime location | `Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe` | Correct |
| Re-invocation guard | Scripts detect PS5 and re-invoke via bundled PS7 | Correct; described as an auto-correction path, not supported fallback |
| Absent bundled runtime | Falls back to system PS7, then errors if not found | Correct |

---

## PS5 Reference Classification

| Reference type | Count | Classification |
|---|---|---|
| "Windows PowerShell 5.1 is not a supported host" | 1 | Correct negative — not a recommendation |
| PS5 re-invocation guard pattern | Multiple in root PS1 wrappers | Correct — guard detects PS5 and re-launches; does not treat PS5 as primary |
| Historical changelog mentions | 0 in active docs | N/A |

No document says "use PowerShell 5" or implies PS5 is preferred.

---

## Root Wrapper Pattern

The re-invocation guard pattern in root `.ps1` wrappers:

```powershell
if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = "Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe"
    & $pwsh -File $PSCommandPath @args
    exit $LASTEXITCODE
}
```

This pattern is:
- A detection-and-redirect, not a PS5 execution path
- Documented in `POWERSHELL_HOST_EXPECTATIONS.md` as the "re-invocation guard"
- Correctly described as an upgrade path, not a fallback that leaves the script running in PS5

**Assessment**: Pattern is correct and correctly documented.

---

## Acceptance Criteria

| Criterion | Status |
|---|---|
| Bundled PS7.6.0 documented as preferred | Pass |
| PS5 references classified as fallback or historical | Pass — PS5 triggers re-invocation; classified as auto-detected, not preferred |
| No "PS5 is the preferred host" language | Pass — opposite is stated explicitly |
| No doc changes needed | Pass |

---

## Conclusion

PowerShell host wording is correct throughout. No changes needed. The re-invocation guard in `SmokeTests/` wrappers matches the documented policy in `POWERSHELL_HOST_EXPECTATIONS.md`.

---

## Task Output

```
Task ID: CLN-021
Files inspected: Docs\POWERSHELL_HOST_EXPECTATIONS.md, root *.ps1 wrappers (re-invocation guard pattern)
Files changed: Docs\POWERSHELL_HOST_WORDING_AUDIT.md (created)
Validation: Read POWERSHELL_HOST_EXPECTATIONS.md lines 1-60. Cross-referenced re-invocation guard pattern.
Findings: All wording is correct. PS7.6.0 is documented as preferred; PS5 is auto-detected and re-invoked, not accepted as host.
Open questions: None.
Risk: Low — documentation only.
```

