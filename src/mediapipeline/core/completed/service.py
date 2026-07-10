from __future__ import annotations

import time
from pathlib import Path

from mediapipeline.core.kernel.config_keys import KEY_OUTSOURCE
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.completed.contracts import CompletedJobRecord
from mediapipeline.core.completed.backfill import (
    build_completed_backfill_args,
    completed_backfill_launch_exception_message,
    completed_backfill_result_message,
    completed_backfill_script_path,
    validate_completed_backfill_request,
)
from mediapipeline.core.completed.manifest import (
    DEFAULT_COMPLETED_PROOF_MODE,
    normalize_proof_mode,
    read_completed_manifest_records,
)
from mediapipeline.core.kernel.runtime.subprocess_runner import run_capture


COMPLETED_HISTORY_CACHE_SECONDS = 60.0
COMPLETED_HISTORY_LIMIT = 500


class CompletedJobsServiceMixin:
    def outsource_root(self, resolved: ResolvedPaths) -> Path | None:
        return self._path_or_none(resolved.config_data.get(KEY_OUTSOURCE))

    def load_recent_completed_jobs(
        self,
        resolved: ResolvedPaths,
        *,
        limit: int | None = COMPLETED_HISTORY_LIMIT,
        force_refresh: bool = False,
        proof_mode: str = DEFAULT_COMPLETED_PROOF_MODE,
    ) -> list[CompletedJobRecord]:
        """Read completed jobs from the local append-only JSONL manifest.

        The manifest at ``<LocalBase>/State/Completed/completed_jobs.jsonl`` is
        written by the pipeline itself (see Add-CompletedJobsManifestEntry
        in ops/pipeline/engine/publish/sidecar.ps1) or populated by the Backfill button,
        which runs Backfill-CompletedManifest.ps1. Reading a local file is
        trivially fast; the earlier SMB-walk approach that this replaced
        was unreliable on UNC shares (30s+ scans, intermittent timeouts).
        """
        manifest_path = resolved.completed_manifest_path
        if not manifest_path:
            self._completed_history_cache_key = None
            self._completed_history_cache_limit_key = ""
            self._completed_history_cache_proof_key = ""
            self._completed_history_cached_at = 0.0
            self._completed_history_records = []
            self._completed_history_parse_health = {
                "schema_version": "completed_manifest_parse_health.v1",
                "available": True,
                "scope": "absent",
                "complete": True,
                "scanned_line_count": 0,
                "parsed_count": 0,
                "skipped_count": 0,
                "error_count": 0,
                "recent_errors": [],
            }
            return []

        cache_key = str(manifest_path).casefold()
        cache_limit_key = "all" if limit is None else str(limit)
        cache_proof_key = normalize_proof_mode(proof_mode)
        # Invalidate the cache if the manifest file has been rewritten
        # (e.g. by a backfill). mtime is cheap and avoids stale reads
        # after the user clicks Backfill.
        try:
            manifest_mtime = manifest_path.stat().st_mtime if manifest_path.exists() else 0.0
        except OSError:
            manifest_mtime = 0.0
        now = time.monotonic()
        if (
            not force_refresh
            and cache_key == self._completed_history_cache_key
            and cache_limit_key == getattr(self, "_completed_history_cache_limit_key", "")
            and cache_proof_key == getattr(self, "_completed_history_cache_proof_key", "")
            and manifest_mtime == getattr(self, "_completed_history_manifest_mtime", 0.0)
            and (now - self._completed_history_cached_at) < COMPLETED_HISTORY_CACHE_SECONDS
        ):
            if limit is None:
                return list(self._completed_history_records)
            return list(self._completed_history_records[:limit])

        records: list[CompletedJobRecord] = []
        if manifest_path.exists():
            # Read the whole file; at ~400 bytes per entry, even 50k jobs is
            # only ~20 MB. We keep records in append order, then reverse so
            # the most recent job is first — the UI applies its own sort but
            # this keeps the default view chronological-descending.
            try:
                parse_health: dict[str, object] = {}
                records = read_completed_manifest_records(
                    manifest_path,
                    limit=limit,
                    logger=self.logger,
                    proof_mode=proof_mode,
                    parse_health=parse_health,
                )
                self._completed_history_parse_health = parse_health
            except OSError as exc:
                # Persist the mtime sentinel even on a read failure so the
                # auto-poll in _apply_poll does not hammer a transiently
                # unreadable file every 2 seconds. The sentinel is reset to
                # 0.0 by a successful backfill or forced refresh, which is
                # the correct trigger to try again.
                self._completed_history_manifest_mtime = manifest_mtime
                raise RuntimeError(
                    f"Unable to read completed-jobs manifest: {manifest_path} ({exc})"
                ) from exc
        else:
            self._completed_history_parse_health = {
                "schema_version": "completed_manifest_parse_health.v1",
                "available": True,
                "manifest_path": str(manifest_path),
                "scope": "absent",
                "complete": True,
                "scanned_line_count": 0,
                "parsed_count": 0,
                "skipped_count": 0,
                "error_count": 0,
                "recent_errors": [],
            }

        self._completed_history_cache_key = cache_key
        self._completed_history_cache_limit_key = cache_limit_key
        self._completed_history_cache_proof_key = cache_proof_key
        self._completed_history_cached_at = now
        self._completed_history_manifest_mtime = manifest_mtime
        self._completed_history_records = list(records)
        # Diagnostic counters used by the UI "No entries found" message.
        self._completed_scan_dirs_visited = -2  # sentinel: manifest mode
        self._completed_scan_sidecars_found = len(records)
        # The JSON manifest is the authoritative completed-job source. The GET
        # read path no longer mirrors rows into the SQLite shadow table: that
        # mirror has no reader, and the per-row commit dominated broad-refresh
        # load time (~8s on the investigated state). The mirror stays available
        # via mediapipeline.core.storage.db.open_state_db().record_completed_job for an explicit
        # maintenance/backfill or a future write-path sync.
        # (backend-load-performance Packet 2.)
        return list(records)

    def backfill_completed_manifest(
        self,
        resolved: ResolvedPaths,
        *,
        timeout_seconds: float = 120.0,
        dry_run: bool = False,
        checkpoint_path: Path | str | None = None,
    ) -> tuple[bool, str]:
        """Run Backfill-CompletedManifest.ps1 to rebuild the local manifest
        from outsource sidecars. Returns (success, message).

        Invoked from the Completed tab's "Backfill" button. This is the one
        slow operation we still allow against the SMB share — it runs once
        when the user opts into it, never automatically.
        """
        outsource = self.outsource_root(resolved)
        script = completed_backfill_script_path(resolved)
        ok, message = validate_completed_backfill_request(resolved, outsource=outsource, script_path=script)
        if not ok:
            return False, message

        try:
            assert outsource is not None
            args = build_completed_backfill_args(
                resolved,
                outsource=outsource,
                script_path=script,
                dry_run=dry_run,
                checkpoint_path=checkpoint_path,
            )
            result = run_capture(
                args,
                timeout_seconds=timeout_seconds,
                hidden=True,
                label="completed manifest backfill",
                kill_tree=getattr(self, "kill_process_tree", None),
            )
        except Exception as exc:
            return False, completed_backfill_launch_exception_message(exc)

        ok, message = completed_backfill_result_message(result, timeout_seconds)
        if not ok:
            return False, message
        # Invalidate the cache so the very next load re-reads the fresh manifest.
        self._completed_history_cache_key = None
        self._completed_history_cache_limit_key = ""
        self._completed_history_manifest_mtime = 0.0
        return True, message
