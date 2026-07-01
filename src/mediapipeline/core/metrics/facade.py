"""Read-only metrics facade adapter."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from typing import Any

from mediapipeline.core.completed.manifest import PROOF_MODE_SUMMARY
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.completed.contracts import CompletedJobRecord

from .policy import build_metrics_payload
from .sources import (
    load_metrics_backfill_records,
    metrics_source_state_payload,
    run_metrics_sidecar_backfill,
    update_metrics_sources,
)

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_commands import CommandResult


def _command_result(**fields: Any) -> "CommandResult":
    from mediapipeline.core.kernel.dto_commands import CommandResult

    return CommandResult(**fields)


class MetricsFacadeMixin:
    """Aggregate backend-owned read models into the Metrics page payload."""

    service: object

    def get_metrics(self, resolved: ResolvedPaths) -> dict[str, Any]:
        warnings: list[str] = []
        completed_records = self._metrics_completed_records(resolved, warnings)
        backfill_records, source_backfill = load_metrics_backfill_records(resolved, warnings)
        records = self._metrics_merged_records(completed_records, backfill_records)
        pending_payload = self._metrics_pending_publish(resolved, warnings)
        workers_payload = self._metrics_network_workers(resolved, warnings)
        final_library_payload = self._metrics_final_library(resolved, records, warnings)
        return build_metrics_payload(
            records,
            pending_publish=pending_payload,
            network_workers=workers_payload,
            final_library=final_library_payload,
            source_backfill=source_backfill,
            completed_source=str(resolved.completed_manifest_path or ""),
            warnings=warnings,
        )

    def save_metrics_sources(self, resolved: ResolvedPaths, request: dict[str, Any]) -> "CommandResult":
        lock = getattr(self, "_metrics_state_lock", None)
        context = lock if lock is not None else nullcontext()
        with context:
            result = update_metrics_sources(resolved, request)
        return _command_result(
            command="metrics.sources",
            ok=bool(result.get("ok")),
            message=str(result.get("message") or ""),
            severity=str(result.get("severity") or "info"),
            warnings=[str(item) for item in result.get("warnings") or []],
            errors=[str(item) for item in result.get("errors") or []],
            refresh_hint="metrics",
            data=dict(result.get("data") or {}),
        )

    def run_metrics_backfill(self, resolved: ResolvedPaths, request: dict[str, Any]) -> "CommandResult":
        lock = getattr(self, "_metrics_state_lock", None)
        context = lock if lock is not None else nullcontext()
        with context:
            result = run_metrics_sidecar_backfill(resolved, request)
        return _command_result(
            command="metrics.backfill",
            ok=bool(result.get("ok")),
            message=str(result.get("message") or ""),
            severity=str(result.get("severity") or "info"),
            warnings=[str(item) for item in result.get("warnings") or []],
            errors=[str(item) for item in result.get("errors") or []],
            refresh_hint="metrics",
            data=dict(result.get("data") or {}),
        )

    def _metrics_merged_records(
        self,
        completed_records: list[CompletedJobRecord],
        backfill_records: list[CompletedJobRecord],
    ) -> list[CompletedJobRecord]:
        seen: set[tuple[str, ...]] = set()
        merged: list[CompletedJobRecord] = []
        for record in [*completed_records, *backfill_records]:
            key = self._metrics_record_identity(record)
            if key in seen:
                continue
            seen.add(key)
            merged.append(record)
        oldest = datetime.min.replace(tzinfo=timezone.utc)
        return sorted(merged, key=lambda item: item.completed_at or oldest, reverse=True)

    def _metrics_record_identity(self, record: CompletedJobRecord) -> tuple[str, ...]:
        source_identity = str(record.payload.get("source_identity_v2") or "").strip()
        source_path = record.source_path_text.casefold()
        output_path = str(record.payload.get("output_path") or record.output_path).strip().casefold()
        encoded_at = str(record.payload.get("encoded_at") or "").strip()
        route = record.route
        if source_identity or source_path or output_path or encoded_at or route:
            return (
                "logical",
                source_identity or source_path,
                output_path,
                encoded_at,
                route,
            )
        return ("sidecar", str(record.sidecar_path).casefold())

    def _metrics_completed_records(self, resolved: ResolvedPaths, warnings: list[str]) -> list[CompletedJobRecord]:
        loader = getattr(self.service, "load_recent_completed_jobs", None)
        if not callable(loader):
            warnings.append("Completed metrics unavailable: completed history service is not available.")
            return []
        try:
            return list(
                loader(
                    resolved,
                    limit=None,
                    force_refresh=False,
                    proof_mode=PROOF_MODE_SUMMARY,
                )
            )
        except TypeError:
            try:
                return list(loader(resolved, limit=None, force_refresh=False))
            except Exception as exc:
                warnings.append(f"Completed metrics unavailable: {exc}")
                return []
        except Exception as exc:
            warnings.append(f"Completed metrics unavailable: {exc}")
            return []

    def _metrics_pending_publish(self, resolved: ResolvedPaths, warnings: list[str]) -> dict[str, Any]:
        try:
            return self.get_pending_publish_preview(resolved).to_mapping()  # type: ignore[attr-defined]
        except Exception as exc:
            warnings.append(f"Pending-publish metrics unavailable: {exc}")
            return {
                "schema_version": "desktop_pending_publish_preview.v1",
                "warnings": [str(exc)],
            }

    def _metrics_network_workers(self, resolved: ResolvedPaths, warnings: list[str]) -> dict[str, Any]:
        try:
            return self.get_network_workers(resolved).to_mapping()  # type: ignore[attr-defined]
        except Exception as exc:
            warnings.append(f"Worker metrics unavailable: {exc}")
            return {
                "schema_version": "desktop_network_workers.v1",
                "warnings": [str(exc)],
            }

    def _metrics_final_library(
        self,
        resolved: ResolvedPaths,
        records: list[CompletedJobRecord],
        warnings: list[str],
    ) -> dict[str, Any]:
        reader = getattr(self.service, "get_final_library_promotion_status", None)
        if not callable(reader):
            return {
                "schema_version": "desktop_final_library_promotion_status.v1",
                "enabled": False,
                "counts": {},
                "warnings": ["Final library promotion service is not available."],
            }
        try:
            return dict(reader(resolved, records=records[:500], limit=500))
        except TypeError:
            try:
                return dict(reader(resolved, limit=500))
            except Exception as exc:
                warnings.append(f"Final-library metrics unavailable: {exc}")
                return {
                    "schema_version": "desktop_final_library_promotion_status.v1",
                    "enabled": False,
                    "counts": {},
                    "warnings": [str(exc)],
                }
        except Exception as exc:
            warnings.append(f"Final-library metrics unavailable: {exc}")
            return {
                "schema_version": "desktop_final_library_promotion_status.v1",
                "enabled": False,
                "counts": {},
                "warnings": [str(exc)],
            }


__all__ = [
    "MetricsFacadeMixin",
]
