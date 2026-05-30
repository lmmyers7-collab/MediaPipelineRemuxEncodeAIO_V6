from __future__ import annotations

import threading
import time
from typing import Any, Mapping

from mediapipeline_desktop_app.models import CompletedJobRecord, ResolvedPaths

from .promotion import (
    CONSECUTIVE_FAILURE_LIMIT,
    FINAL_LIBRARY_PROMOTION_RUN_SCHEMA_VERSION,
    build_promotion_item_rows,
    promotion_settings_from_config,
    promotion_status_payload,
    promote_item,
    read_item_evidence,
    utc_now_text,
    write_active_run,
    write_item_evidence,
    write_item_manifest,
    write_run_manifest,
)


class FinalLibraryPromotionServiceMixin:
    def _ensure_final_library_promotion_state(self) -> None:
        if not hasattr(self, "_final_library_promotion_lock"):
            self._final_library_promotion_lock = threading.RLock()
        if not hasattr(self, "_final_library_promotion_active"):
            self._final_library_promotion_active = None

    def _final_library_promotion_snapshot_locked(self) -> dict[str, Any] | None:
        active = getattr(self, "_final_library_promotion_active", None)
        if not isinstance(active, dict):
            return None
        return {
            "schema_version": FINAL_LIBRARY_PROMOTION_RUN_SCHEMA_VERSION,
            "run_id": str(active.get("run_id") or ""),
            "status": str(active.get("status") or ""),
            "pause_state": str(active.get("pause_state") or "running"),
            "pause_requested": bool(active.get("pause_requested", False)),
            "started_at": str(active.get("started_at") or ""),
            "updated_at": str(active.get("updated_at") or ""),
            "current_row_key": str(active.get("current_row_key") or ""),
            "eligible_count": int(active.get("eligible_count") or 0),
            "completed_count": int(active.get("completed_count") or 0),
            "succeeded_count": int(active.get("succeeded_count") or 0),
            "failed_count": int(active.get("failed_count") or 0),
            "consecutive_failures": int(active.get("consecutive_failures") or 0),
            "stop_reason": str(active.get("stop_reason") or ""),
            "warnings": list(active.get("warnings") or []),
            "errors": list(active.get("errors") or []),
            "item_states": dict(active.get("item_states") or {}),
        }

    def _final_library_promotion_active_snapshot(self) -> dict[str, Any] | None:
        self._ensure_final_library_promotion_state()
        with self._final_library_promotion_lock:
            return self._final_library_promotion_snapshot_locked()

    def _write_final_library_active_locked(self, resolved: ResolvedPaths) -> None:
        try:
            write_active_run(resolved, self._final_library_promotion_snapshot_locked())
        except Exception as exc:
            logger = getattr(self, "logger", None)
            if logger is not None:
                logger.warning("Could not write final-library promotion active-run state: %s", exc)

    def get_final_library_promotion_status(
        self,
        resolved: ResolvedPaths,
        *,
        records: list[CompletedJobRecord] | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        self._ensure_final_library_promotion_state()
        if records is None:
            loader = getattr(self, "load_recent_completed_jobs", None)
            records = loader(resolved, limit=limit) if callable(loader) else []
        pending_payload = None
        scanner = getattr(self, "scan_pending_publish", None)
        if callable(scanner):
            try:
                pending_payload = scanner(resolved)
            except Exception:
                pending_payload = None
        return promotion_status_payload(
            resolved,
            records,
            active_run=self._final_library_promotion_active_snapshot(),
            pending_payload=pending_payload,
        )

    def annotate_final_library_promotion_rows(
        self,
        resolved: ResolvedPaths,
        records: list[CompletedJobRecord],
        rows: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        status = self.get_final_library_promotion_status(resolved, records=records)
        items_by_key = {
            str(item.get("row_key") or ""): item
            for item in status.get("items") or []
            if isinstance(item, Mapping)
        }
        annotated: list[dict[str, Any]] = []
        for row in rows:
            copy = dict(row)
            promotion = items_by_key.get(str(copy.get("row_key") or ""))
            if promotion:
                copy.update(promotion)
            annotated.append(copy)
        return annotated, {key: value for key, value in status.items() if key not in {"items", "item_rows"}}

    def start_final_library_promotion_run(
        self,
        resolved: ResolvedPaths,
        records: list[CompletedJobRecord],
    ) -> dict[str, Any]:
        self._ensure_final_library_promotion_state()
        status = self.get_final_library_promotion_status(resolved, records=records)
        eligible_items = [
            dict(item)
            for item in status.get("items") or []
            if isinstance(item, Mapping) and item.get("ready_for_promotion")
        ]
        settings = promotion_settings_from_config(resolved.config_data)
        if not settings.enabled:
            return {
                "ok": False,
                "message": "Final Library Promotion is disabled in Settings.",
                "errors": ["promotion_disabled"],
                "data": status,
            }
        if not eligible_items:
            return {
                "ok": False,
                "message": "No completed output rows are eligible for final-library promotion.",
                "errors": ["no_eligible_items"],
                "data": status,
            }

        run_id = "flp-" + utc_now_text().replace(":", "").replace("+", "z").replace("-", "").replace("T", "-")
        with self._final_library_promotion_lock:
            active = getattr(self, "_final_library_promotion_active", None)
            if isinstance(active, dict) and str(active.get("status") or "") in {"running", "pausing", "paused"}:
                return {
                    "ok": False,
                    "message": f"Final library promotion run {active.get('run_id')} is already active.",
                    "errors": ["promotion_already_active"],
                    "data": self._final_library_promotion_snapshot_locked() or {},
                }
            self._final_library_promotion_active = {
                "run_id": run_id,
                "status": "running",
                "pause_state": "running",
                "pause_requested": False,
                "started_at": utc_now_text(),
                "updated_at": utc_now_text(),
                "current_row_key": "",
                "eligible_count": len(eligible_items),
                "completed_count": 0,
                "succeeded_count": 0,
                "failed_count": 0,
                "consecutive_failures": 0,
                "stop_reason": "",
                "warnings": list(status.get("warnings") or []),
                "errors": [],
                "item_states": {},
            }
            thread = threading.Thread(
                target=self._final_library_promotion_worker,
                args=(resolved, run_id, eligible_items, settings.to_mapping()),
                name=f"FinalLibraryPromotion-{run_id}",
                daemon=True,
            )
            self._final_library_promotion_active["thread"] = thread
            self._write_final_library_active_locked(resolved)
            thread.start()
            snapshot = self._final_library_promotion_snapshot_locked() or {}

        return {
            "ok": True,
            "message": f"Started final-library promotion run {run_id} for {len(eligible_items)} item(s).",
            "warnings": list(status.get("warnings") or []),
            "data": snapshot,
        }

    def _final_library_pause_before_next_item(self, resolved: ResolvedPaths, run_id: str) -> bool:
        while True:
            with self._final_library_promotion_lock:
                active = getattr(self, "_final_library_promotion_active", None)
                if not isinstance(active, dict) or active.get("run_id") != run_id:
                    return False
                if not active.get("pause_requested"):
                    if active.get("pause_state") == "paused":
                        active["pause_state"] = "running"
                        active["status"] = "running"
                        active["updated_at"] = utc_now_text()
                        self._write_final_library_active_locked(resolved)
                    return True
                active["status"] = "paused"
                active["pause_state"] = "paused"
                active["updated_at"] = utc_now_text()
                self._write_final_library_active_locked(resolved)
            time.sleep(0.25)

    def _final_library_promotion_worker(
        self,
        resolved: ResolvedPaths,
        run_id: str,
        eligible_items: list[dict[str, Any]],
        settings_snapshot: dict[str, Any],
    ) -> None:
        settings = promotion_settings_from_config(
            {
                **resolved.config_data,
                "FinalLibraryPromotionEnabled": settings_snapshot.get("enabled"),
                "FinalLibraryPromotionRules": settings_snapshot.get("rules"),
                "FinalLibraryPromotionVerificationMode": settings_snapshot.get("verification_mode"),
                "FinalLibraryPromotionCleanupAfterVerified": settings_snapshot.get("cleanup_after_verified"),
                "FinalLibraryPromotionOverwriteExisting": settings_snapshot.get("overwrite_existing"),
                "Outsource": settings_snapshot.get("publish_root"),
            }
        )
        item_evidence = read_item_evidence(resolved)
        run_manifest: dict[str, Any] = {
            "schema_version": FINAL_LIBRARY_PROMOTION_RUN_SCHEMA_VERSION,
            "run_id": run_id,
            "started_at": utc_now_text(),
            "settings_snapshot": settings_snapshot,
            "items": [],
            "stop_reason": "",
            "completed_at": "",
        }
        consecutive_failures = 0
        try:
            for item in eligible_items:
                if not self._final_library_pause_before_next_item(resolved, run_id):
                    break
                row_key = str(item.get("row_key") or "")
                with self._final_library_promotion_lock:
                    active = getattr(self, "_final_library_promotion_active", None)
                    if not isinstance(active, dict) or active.get("run_id") != run_id:
                        break
                    active["status"] = "running"
                    active["pause_state"] = "running"
                    active["current_row_key"] = row_key
                    active["updated_at"] = utc_now_text()
                    active.setdefault("item_states", {})[row_key] = {"status": "promoting"}
                    self._write_final_library_active_locked(resolved)

                evidence = promote_item(item, settings)
                evidence["run_id"] = run_id
                evidence["settings_snapshot"] = settings_snapshot
                evidence["rule_id"] = item.get("final_library_rule_id") or ""
                evidence["rule_label"] = item.get("final_library_rule_label") or ""
                item_manifest_path = write_item_manifest(resolved, run_id, row_key, evidence)
                evidence["evidence_path"] = str(item_manifest_path)
                run_manifest["items"].append(evidence)

                success = bool(evidence.get("success"))
                if success:
                    consecutive_failures = 0
                    item_evidence[row_key] = evidence
                    item_state = "promoted_cleaned" if evidence.get("cleanup_result", {}).get("completed") else "promoted"
                else:
                    consecutive_failures += 1
                    item_state = "promotion_failed"

                with self._final_library_promotion_lock:
                    active = getattr(self, "_final_library_promotion_active", None)
                    if isinstance(active, dict) and active.get("run_id") == run_id:
                        active["completed_count"] = int(active.get("completed_count") or 0) + 1
                        active["succeeded_count"] = int(active.get("succeeded_count") or 0) + (1 if success else 0)
                        active["failed_count"] = int(active.get("failed_count") or 0) + (0 if success else 1)
                        active["consecutive_failures"] = consecutive_failures
                        active["current_row_key"] = ""
                        active["updated_at"] = utc_now_text()
                        active.setdefault("item_states", {})[row_key] = {
                            "status": item_state,
                            "error": "; ".join(str(failure) for failure in evidence.get("failures") or []),
                        }
                        if consecutive_failures >= CONSECUTIVE_FAILURE_LIMIT:
                            active["status"] = "stopped_after_failures"
                            active["stop_reason"] = "Stopped after 3 consecutive failed promotion items."
                        self._write_final_library_active_locked(resolved)

                if success:
                    write_item_evidence(resolved, item_evidence)
                if consecutive_failures >= CONSECUTIVE_FAILURE_LIMIT:
                    run_manifest["stop_reason"] = "Stopped after 3 consecutive failed promotion items."
                    break
        except Exception as exc:
            run_manifest["stop_reason"] = f"Promotion worker failed: {exc}"
            with self._final_library_promotion_lock:
                active = getattr(self, "_final_library_promotion_active", None)
                if isinstance(active, dict) and active.get("run_id") == run_id:
                    active["status"] = "failed"
                    active.setdefault("errors", []).append(str(exc))
                    active["updated_at"] = utc_now_text()
                    self._write_final_library_active_locked(resolved)
        finally:
            run_manifest["completed_at"] = utc_now_text()
            write_run_manifest(resolved, run_id, run_manifest)
            with self._final_library_promotion_lock:
                active = getattr(self, "_final_library_promotion_active", None)
                if isinstance(active, dict) and active.get("run_id") == run_id:
                    active["updated_at"] = utc_now_text()
                    self._final_library_promotion_active = None
                    self._write_final_library_active_locked(resolved)

    def pause_final_library_promotion_run(self, run_id: str, resolved: ResolvedPaths) -> dict[str, Any]:
        self._ensure_final_library_promotion_state()
        with self._final_library_promotion_lock:
            active = getattr(self, "_final_library_promotion_active", None)
            if not isinstance(active, dict) or str(active.get("run_id") or "") != run_id:
                return {
                    "ok": False,
                    "message": "No active final-library promotion run matches the requested run_id.",
                    "errors": ["promotion_run_not_active"],
                    "data": {},
                }
            active["pause_requested"] = True
            if active.get("status") == "running":
                active["status"] = "pausing"
                active["pause_state"] = "pausing"
            active["updated_at"] = utc_now_text()
            self._write_final_library_active_locked(resolved)
            snapshot = self._final_library_promotion_snapshot_locked() or {}
        return {
            "ok": True,
            "message": f"Pause requested for final-library promotion run {run_id}.",
            "data": snapshot,
        }

    def resume_final_library_promotion_run(self, run_id: str, resolved: ResolvedPaths) -> dict[str, Any]:
        self._ensure_final_library_promotion_state()
        with self._final_library_promotion_lock:
            active = getattr(self, "_final_library_promotion_active", None)
            if not isinstance(active, dict) or str(active.get("run_id") or "") != run_id:
                return {
                    "ok": False,
                    "message": "No active final-library promotion run matches the requested run_id.",
                    "errors": ["promotion_run_not_active"],
                    "data": {},
                }
            active["pause_requested"] = False
            active["pause_state"] = "running"
            active["status"] = "running"
            active["updated_at"] = utc_now_text()
            self._write_final_library_active_locked(resolved)
            snapshot = self._final_library_promotion_snapshot_locked() or {}
        return {
            "ok": True,
            "message": f"Resumed final-library promotion run {run_id}.",
            "data": snapshot,
        }

    def final_library_promotion_active_block_message(self, action: str) -> str:
        self._ensure_final_library_promotion_state()
        with self._final_library_promotion_lock:
            active = getattr(self, "_final_library_promotion_active", None)
            if not isinstance(active, dict):
                return ""
            status = str(active.get("status") or "").strip()
            if status in {"running", "pausing", "paused"}:
                return f"{action} blocked because final-library promotion run {active.get('run_id')} is {status}."
        return ""


__all__ = ["FinalLibraryPromotionServiceMixin"]
