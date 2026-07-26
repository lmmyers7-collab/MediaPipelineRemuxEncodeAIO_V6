"""Reject tracked Office working documents under the active documentation tree."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
GIT_ENUMERATION_TIMEOUT_SECONDS = 15
OFFICE_DOCUMENT_EXTENSIONS = frozenset(
    {
        ".doc",
        ".docm",
        ".docx",
        ".dotx",
        ".pptm",
        ".pptx",
        ".xlsm",
        ".xlsx",
    }
)


class GitEnumerationError(RuntimeError):
    """Raised when Git cannot authoritatively enumerate tracked documentation."""


def tracked_office_documents(root: Path = REPO_ROOT) -> list[str]:
    """Return present Office documents tracked below ``docs/``.

    A path deleted in the worktree is ignored so this check can validate an
    unstaged remediation; Git will remove that path from the index when the
    deletion is staged or committed.
    """

    command = ["git", "ls-files", "-z", "--", "docs"]
    try:
        result = subprocess.run(
            command,
            cwd=root,
            check=True,
            text=True,
            capture_output=True,
            timeout=GIT_ENUMERATION_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise GitEnumerationError("Git executable is unavailable.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitEnumerationError(
            f"Git tracked-document enumeration timed out after {GIT_ENUMERATION_TIMEOUT_SECONDS} seconds."
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = str(exc.stderr or exc.stdout or "").strip()
        suffix = f": {detail}" if detail else ""
        raise GitEnumerationError(
            f"Git tracked-document enumeration failed with exit {exc.returncode}{suffix}"
        ) from exc
    except OSError as exc:
        raise GitEnumerationError(f"Git tracked-document enumeration could not run: {exc}") from exc

    findings: list[str] = []
    for raw_path in result.stdout.split("\0"):
        relative = raw_path.strip().replace("\\", "/")
        if not relative:
            continue
        if Path(relative).suffix.casefold() not in OFFICE_DOCUMENT_EXTENSIONS:
            continue
        if (root / Path(relative)).is_file():
            findings.append(relative)
    return sorted(set(findings), key=str.casefold)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    try:
        findings = tracked_office_documents(args.root.resolve())
    except GitEnumerationError as exc:
        if args.json:
            print(json.dumps({"ok": False, "findings": [], "error": str(exc)}, indent=2))
        else:
            print(f"Tracked Office document check failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"ok": not findings, "findings": findings, "error": ""}, indent=2))
    elif findings:
        print("Tracked Office working documents are not allowed under docs/:", file=sys.stderr)
        for path in findings:
            print(f"- {path}", file=sys.stderr)
        print(
            "Convert project-owned notes to Markdown or document and review an explicit provenance-policy exception.",
            file=sys.stderr,
        )
    else:
        print("Tracked Office document check passed.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
