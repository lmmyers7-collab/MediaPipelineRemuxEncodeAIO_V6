"""Generate the config JSON Schema from `app.contracts.config`.

Use `--check` in CI/pre-commit to fail when `schemas/config.v1.schema.json`
is stale.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "config.v1.schema.json"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def render_schema() -> str:
    from app.contracts.config import CONFIG_SCHEMA_VERSION, Config

    schema = Config.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://local.mediapipeline/schemas/config.v1.schema.json"
    schema["title"] = "MediaPipeline Config"
    schema["x-config-schema-version"] = CONFIG_SCHEMA_VERSION
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
    print("Config schema drift detected. Regenerate with:")
    print("  python scripts/dev/generate_config_schema.py")
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
