from __future__ import annotations

from typing import Any

from mediapipeline_desktop_app.application.dto import CommandResult
from mediapipeline_desktop_app.models import ResolvedPaths


class FinalLibraryPromotionFacadeMixin:
    service: object

    def get_final_library_promotion_status(self, resolved: ResolvedPaths, limit: int = 500) -> dict[str, Any]:
        reader = getattr(self.service, "get_final_library_promotion_status", None)
        if not callable(reader):
            return {
                "schema_version": "desktop_final_library_promotion_status.v1",
                "enabled": False,
                "counts": {},
                "items": [],
                "item_rows": [],
                "warnings": ["Final library promotion service is not available."],
            }
        return reader(resolved, limit=limit)

    def start_final_library_promotion(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        if request.get("confirm_promote") is not True:
            return CommandResult(
                command="final_library.promote_queue",
                ok=False,
                severity="error",
                message="Final-library promotion requires confirm_promote=true.",
                errors=["missing_confirm_promote"],
            )
        block_message = self._active_work_block_message(resolved, "Final library promotion")
        if block_message:
            return CommandResult(
                command="final_library.promote_queue",
                ok=False,
                severity="error",
                message=block_message,
                errors=["active_work"],
            )
        loader = getattr(self.service, "load_recent_completed_jobs", None)
        starter = getattr(self.service, "start_final_library_promotion_run", None)
        if not callable(loader) or not callable(starter):
            return CommandResult(
                command="final_library.promote_queue",
                ok=False,
                severity="error",
                message="Final-library promotion service is not available.",
                errors=["service_unavailable"],
            )
        try:
            records = loader(resolved, limit=500, force_refresh=True)
            result = starter(resolved, records)
        except Exception as exc:
            return CommandResult(
                command="final_library.promote_queue",
                ok=False,
                severity="error",
                message=f"Final-library promotion could not start: {exc}",
                errors=[str(exc)],
            )
        return CommandResult(
            command="final_library.promote_queue",
            ok=bool(result.get("ok")),
            severity="info" if result.get("ok") else "error",
            message=str(result.get("message") or ""),
            warnings=[str(item) for item in result.get("warnings") or []],
            errors=[str(item) for item in result.get("errors") or []],
            data=dict(result.get("data") or {}),
            refresh_hint="completed",
        )

    def pause_final_library_promotion(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        run_id = str(request.get("run_id") or "").strip()
        if not run_id:
            return CommandResult(
                command="final_library.pause",
                ok=False,
                severity="error",
                message="Pause requires the current promotion run_id.",
                errors=["missing_run_id"],
            )
        pauser = getattr(self.service, "pause_final_library_promotion_run", None)
        if not callable(pauser):
            return CommandResult(
                command="final_library.pause",
                ok=False,
                severity="error",
                message="Final-library promotion service is not available.",
                errors=["service_unavailable"],
            )
        result = pauser(run_id, resolved)
        return CommandResult(
            command="final_library.pause",
            ok=bool(result.get("ok")),
            severity="info" if result.get("ok") else "error",
            message=str(result.get("message") or ""),
            errors=[str(item) for item in result.get("errors") or []],
            data=dict(result.get("data") or {}),
            refresh_hint="completed",
        )

    def resume_final_library_promotion(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        run_id = str(request.get("run_id") or "").strip()
        if not run_id:
            return CommandResult(
                command="final_library.resume",
                ok=False,
                severity="error",
                message="Resume requires the current promotion run_id.",
                errors=["missing_run_id"],
            )
        resumer = getattr(self.service, "resume_final_library_promotion_run", None)
        if not callable(resumer):
            return CommandResult(
                command="final_library.resume",
                ok=False,
                severity="error",
                message="Final-library promotion service is not available.",
                errors=["service_unavailable"],
            )
        result = resumer(run_id, resolved)
        return CommandResult(
            command="final_library.resume",
            ok=bool(result.get("ok")),
            severity="info" if result.get("ok") else "error",
            message=str(result.get("message") or ""),
            errors=[str(item) for item in result.get("errors") or []],
            data=dict(result.get("data") or {}),
            refresh_hint="completed",
        )


__all__ = ["FinalLibraryPromotionFacadeMixin"]
