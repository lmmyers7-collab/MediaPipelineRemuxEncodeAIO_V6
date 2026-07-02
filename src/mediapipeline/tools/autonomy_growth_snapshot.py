from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from mediapipeline.core.diagnostics.autonomy_health import load_autonomy_growth_history, record_autonomy_growth_snapshot
from mediapipeline.tools.autonomy_health_gate import build_health_from_payload, resolved_paths_from_payload


def _read_payload(args: argparse.Namespace) -> Mapping[str, Any]:
    if args.paths_json_file:
        raw = Path(args.paths_json_file).read_text(encoding="utf-8-sig")
    else:
        raw = str(args.paths_json or "").strip()
    if not raw:
        raise ValueError("paths JSON payload is required")
    payload = json.loads(raw)
    if not isinstance(payload, Mapping):
        raise ValueError("paths JSON root must be an object")
    return payload


def record_snapshot_from_payload(payload: Mapping[str, Any], *, max_snapshots: int = 64) -> dict[str, Any]:
    resolved = resolved_paths_from_payload(payload)
    health = build_health_from_payload(payload)
    write_result = record_autonomy_growth_snapshot(resolved, health, max_snapshots=max_snapshots)
    history = load_autonomy_growth_history(resolved, max_snapshots=max_snapshots)
    ok = bool(write_result.get("wrote_snapshot"))
    return {
        "schema_version": "desktop_autonomy_growth_snapshot_cli.v1",
        "ok": ok,
        "effect": "diagnostics_state_snapshot_write",
        "health": health,
        "write_result": write_result,
        "history": {
            "schema_version": history.get("schema_version"),
            "snapshot_path": history.get("snapshot_path"),
            "snapshot_count": history.get("snapshot_count"),
            "total_snapshot_count": history.get("total_snapshot_count"),
            "invalid_line_count": history.get("invalid_line_count"),
            "max_snapshot_count": history.get("max_snapshot_count"),
            "read_error": history.get("read_error"),
        },
        "media_mutation_performed": False,
        "pending_publish_mutation_performed": False,
        "queue_mutation_performed": False,
        "cleanup_performed": False,
        "policy": (
            "Explicit autonomy growth snapshot write. This CLI records diagnostics-state trend evidence only; "
            "it does not mutate sources, pending publish, queue state, cleanup targets, or media policy."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record a bounded MediaPipeline autonomy growth snapshot.")
    parser.add_argument("--paths-json", default="", help="Resolved path payload JSON.")
    parser.add_argument("--paths-json-file", default="", help="File containing resolved path payload JSON.")
    parser.add_argument("--max-snapshots", type=int, default=64, help="Maximum retained growth snapshots.")
    args = parser.parse_args(argv)
    try:
        payload = record_snapshot_from_payload(_read_payload(args), max_snapshots=args.max_snapshots)
    except Exception as exc:
        payload = {
            "schema_version": "desktop_autonomy_growth_snapshot_cli_error.v1",
            "ok": False,
            "error": str(exc),
            "media_mutation_performed": False,
            "pending_publish_mutation_performed": False,
            "queue_mutation_performed": False,
            "cleanup_performed": False,
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "main",
    "record_snapshot_from_payload",
]
