"""Generate the stage JSON Schema from `mediapipeline.contracts.stages`.

Use `--check` in CI/pre-commit to fail when `src/mediapipeline/contracts/schemas/stages.v1.schema.json`
is stale.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

REPO_ROOT = find_repo_root(Path(__file__))
SCHEMA_PATH = REPO_ROOT / "src" / "mediapipeline" / "contracts" / "schemas" / "stages.v1.schema.json"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def render_schema() -> str:
    from mediapipeline.contracts.stages import STAGE_SCHEMA_VERSION, StageContractSchema

    schema = StageContractSchema.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://local.mediapipeline/src/mediapipeline/contracts/schemas/stages.v1.schema.json"
    schema["title"] = "MediaPipeline Stage Contracts"
    schema["x-stage-schema-version"] = STAGE_SCHEMA_VERSION
    return json.dumps(schema, indent=2) + "\n"


def write_if_changed(path: Path, text: str) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def check_current(path: Path, expected: str) -> int:
    actual = path.read_text(encoding="utf-8") if path.exists() else ""
    if actual == expected:
        print(f"OK: {path.relative_to(REPO_ROOT)} is current")
        return 0
    diff = difflib.unified_diff(
        actual.splitlines(),
        expected.splitlines(),
        fromfile=str(path.relative_to(REPO_ROOT)),
        tofile=f"{path.relative_to(REPO_ROOT)} (generated)",
        lineterm="",
    )
    print("Stage schema drift detected. Regenerate with:")
    print("  python -m mediapipeline.tools.dev.generate_stage_schema")
    print("\n".join(diff))
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated schema is stale")
    args = parser.parse_args(argv)

    expected = render_schema()
    if args.check:
        return check_current(SCHEMA_PATH, expected)
    changed = write_if_changed(SCHEMA_PATH, expected)
    status = "updated" if changed else "current"
    print(f"{SCHEMA_PATH.relative_to(REPO_ROOT)} {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
