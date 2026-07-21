"""Generate config JSON Schema artifacts from the authoritative ``Config`` model.

The contracts schema contains the complete desktop/Python config shape.  The
PowerShell-facing mirror intentionally omits ``NETWORK_CONFIG_KEYS`` and uses a
consumer-specific ``$id``; all remaining validation keywords are identical.
Use ``--check`` in CI/pre-commit/release validation to fail when either shipped
artifact is stale.  Schema consumers use the committed artifacts; production
runtime code never imports this developer-only generator.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

REPO_ROOT = find_repo_root(Path(__file__))
CANONICAL_SCHEMA_PATH = REPO_ROOT / "src" / "mediapipeline" / "contracts" / "schemas" / "config.v1.schema.json"
PIPELINE_SCHEMA_PATH = REPO_ROOT / "ops" / "pipeline" / "config" / "schemas" / "media_pipeline_config.schema.json"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def render_schema(*, schema_id: str, excluded_properties: tuple[str, ...] = ()) -> str:
    from mediapipeline.contracts.config import CONFIG_SCHEMA_VERSION, Config

    schema = Config.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = schema_id
    schema["title"] = "MediaPipeline Config"
    schema["x-config-schema-version"] = CONFIG_SCHEMA_VERSION
    excluded = frozenset(excluded_properties)
    if excluded:
        schema["properties"] = {
            name: definition for name, definition in schema["properties"].items() if name not in excluded
        }
        if "required" in schema:
            schema["required"] = [name for name in schema["required"] if name not in excluded]
    return json.dumps(schema, indent=2) + "\n"


def _expected_outputs() -> dict[Path, str]:
    from mediapipeline.contracts.config import NETWORK_CONFIG_KEYS

    return {
        CANONICAL_SCHEMA_PATH: render_schema(
            schema_id="https://local.mediapipeline/src/mediapipeline/contracts/schemas/config.v1.schema.json"
        ),
        PIPELINE_SCHEMA_PATH: render_schema(
            schema_id="https://local.mediapipeline/ops/pipeline/config/schemas/media_pipeline_config.schema.json",
            excluded_properties=NETWORK_CONFIG_KEYS,
        ),
    }


def _write_if_changed(path: Path, text: str) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def _check_current(path: Path, expected: str) -> bool:
    actual = path.read_text(encoding="utf-8") if path.exists() else ""
    if actual == expected:
        print(f"OK: {path.relative_to(REPO_ROOT)} is current")
        return True
    diff = difflib.unified_diff(
        actual.splitlines(),
        expected.splitlines(),
        fromfile=str(path.relative_to(REPO_ROOT)),
        tofile=f"{path.relative_to(REPO_ROOT)} (generated)",
        lineterm="",
    )
    print("Config schema drift detected. Regenerate with:")
    print("  python -m mediapipeline.tools.dev.generate_config_schema")
    print("\n".join(diff))
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated schema is stale")
    args = parser.parse_args(argv)

    outputs = _expected_outputs()
    if args.check:
        results = [_check_current(path, expected) for path, expected in outputs.items()]
        return 0 if all(results) else 1
    for path, expected in outputs.items():
        changed = _write_if_changed(path, expected)
        status = "updated" if changed else "current"
        print(f"{path.relative_to(REPO_ROOT)} {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
