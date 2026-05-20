from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .contracts import ActiveJobRecord, ContractError
from .service_utils import _read_json_file

ReadJsonFileFunc = Callable[[Path], Any]


def format_active_job_summary(
    folder: Path | None,
    *,
    max_items: int = 6,
    read_json_file: ReadJsonFileFunc = _read_json_file,
) -> list[str]:
    if not folder or not folder.exists():
        return ["No ActiveJobs records found."]
    try:
        records = sorted(folder.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError as exc:
        return [f"ActiveJobs unreadable: {exc}"]

    rows: list[str] = []
    for record_path in records[:max_items]:
        try:
            payload = read_json_file(record_path)
        except Exception as exc:
            rows.append(f"{record_path.name}: unreadable ({exc})")
            continue
        if not isinstance(payload, dict):
            rows.append(f"{record_path.name}: unexpected JSON shape")
            continue
        try:
            record = ActiveJobRecord.from_mapping(payload)
        except ContractError as exc:
            if str(payload.get("schema_version") or "").strip():
                rows.append(f"{record_path.name}: invalid active job contract ({exc})")
                continue
            kind = str(payload.get("job_kind") or "job")
            mode = str(payload.get("mode") or "").strip()
            status = str(payload.get("status") or "unknown")
            pid = str(payload.get("pid") or "")
            launched = str(payload.get("launched_at") or "")
            return_code = payload.get("return_code")
        else:
            kind = record.job_kind
            mode = record.mode
            status = record.status
            pid = "" if record.pid is None else str(record.pid)
            launched = record.launched_at
            return_code = record.return_code
        pid_text = f"pid {pid}" if pid else "pid unknown"
        mode_text = f" {mode}" if mode else ""
        rc_text = "" if return_code is None else f" rc={return_code}"
        rows.append(f"{kind}{mode_text}: {status} ({pid_text}){rc_text} launched {launched}")
    return rows or ["ActiveJobs folder is empty."]


def active_job_detail_rows(
    folder: Path | None,
    *,
    max_items: int = 20,
    read_json_file: ReadJsonFileFunc = _read_json_file,
) -> list[dict[str, Any]]:
    if not folder or not folder.exists():
        return []
    try:
        records = sorted(folder.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError as exc:
        return [
            {
                "record_file": "",
                "record_path": str(folder),
                "source": "unreadable",
                "status": "unreadable",
                "issue": f"ActiveJobs unreadable: {exc}",
            }
        ]

    rows: list[dict[str, Any]] = []
    for record_path in records[:max_items]:
        base = {
            "record_file": record_path.name,
            "record_path": str(record_path),
        }
        try:
            payload = read_json_file(record_path)
        except Exception as exc:
            rows.append({**base, "source": "unreadable", "status": "unreadable", "issue": f"unreadable: {exc}"})
            continue
        if not isinstance(payload, dict):
            rows.append({**base, "source": "invalid", "status": "invalid", "issue": "unexpected JSON shape"})
            continue
        try:
            record = ActiveJobRecord.from_mapping(payload)
        except ContractError as exc:
            if str(payload.get("schema_version") or "").strip():
                rows.append(
                    {
                        **base,
                        "source": "invalid",
                        "schema_version": str(payload.get("schema_version") or ""),
                        "launch_id": str(payload.get("launch_id") or ""),
                        "job_kind": str(payload.get("job_kind") or "job"),
                        "mode": str(payload.get("mode") or ""),
                        "status": str(payload.get("status") or "invalid"),
                        "pid": payload.get("pid"),
                        "app_pid": payload.get("app_pid"),
                        "launched_at": str(payload.get("launched_at") or ""),
                        "last_update": str(payload.get("last_update") or ""),
                        "completed_at": str(payload.get("completed_at") or ""),
                        "return_code": payload.get("return_code"),
                        "stdout_log": str(payload.get("stdout_log") or ""),
                        "stderr_log": str(payload.get("stderr_log") or ""),
                        "cwd": str(payload.get("cwd") or ""),
                        "show_console": bool(payload.get("show_console")),
                        "command_line": str(payload.get("command_line") or ""),
                        "issue": f"invalid active job contract: {exc}",
                    }
                )
                continue
            rows.append(
                {
                    **base,
                    "source": "legacy",
                    "schema_version": "",
                    "launch_id": str(payload.get("launch_id") or ""),
                    "job_kind": str(payload.get("job_kind") or "job"),
                    "mode": str(payload.get("mode") or ""),
                    "status": str(payload.get("status") or "unknown"),
                    "pid": payload.get("pid"),
                    "app_pid": payload.get("app_pid"),
                    "launched_at": str(payload.get("launched_at") or ""),
                    "last_update": str(payload.get("last_update") or ""),
                    "completed_at": str(payload.get("completed_at") or ""),
                    "return_code": payload.get("return_code"),
                    "stdout_log": str(payload.get("stdout_log") or ""),
                    "stderr_log": str(payload.get("stderr_log") or ""),
                    "cwd": str(payload.get("cwd") or ""),
                    "show_console": bool(payload.get("show_console")),
                    "command_line": str(payload.get("command_line") or ""),
                    "issue": "legacy active job record; contract validation was not applied",
                }
            )
            continue
        rows.append(
            {
                **base,
                "source": "contract",
                "schema_version": record.schema_version,
                "launch_id": record.launch_id,
                "job_kind": record.job_kind,
                "mode": record.mode,
                "status": record.status,
                "pid": record.pid,
                "app_pid": record.app_pid,
                "launched_at": record.launched_at,
                "last_update": record.last_update,
                "completed_at": record.completed_at,
                "return_code": record.return_code,
                "stdout_log": record.stdout_log,
                "stderr_log": record.stderr_log,
                "cwd": record.cwd,
                "show_console": record.show_console,
                "command_line": record.command_line,
                "args_count": len(record.args),
                "metadata": dict(record.metadata),
                "issue": "",
            }
        )
    return rows
