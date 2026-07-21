from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_network_worker_result_artifact(
    root: Path,
    *,
    job_id: str,
    output_path: Path,
    batch_id: str,
    row_key: str,
) -> Path:
    path = root / "LocalBase" / "State" / "NetworkWorkerResults" / job_id / "worker_result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "SchemaVersion": "local_worker_result.v1",
                "JobKind": "csv_rerun_row",
                "RerunBatchId": batch_id,
                "RerunRowKey": row_key,
                "WorkerClaimId": job_id,
                "WorkerRunId": "phase8-run",
                "Success": True,
                "Status": "processed",
                "OutputPath": str(output_path),
                "OutputSizeBytes": output_path.stat().st_size,
                "PublishState": "published",
                "PublishMode": "handoff",
                "Route": "network_lifecycle_single_file",
            }
        ),
        encoding="utf-8",
    )
    return path
