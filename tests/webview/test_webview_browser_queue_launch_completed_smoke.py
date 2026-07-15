from __future__ import annotations

from datetime import UTC, datetime
import json
import os
import shutil
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.processes.lifecycle_lease import LifecycleLeaseStore
from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.models import Snapshot

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyProc, DummyWorkflowFacadeService, _resolved
    from .webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyProc, DummyWorkflowFacadeService, _resolved
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{threading.get_ident()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _queue_row(
    source: Path,
    *,
    root: Path,
    order: int,
    blocked_reason_code: str = "",
    blocked_reason: str = "",
) -> dict[str, Any]:
    return {
        "global_order": order,
        "phase": "tv",
        "media_kind": "tv",
        "queue_index": order,
        "queue_total": 2,
        "is_priority": False,
        "source_path": str(source),
        "root_path": str(root),
        "relative_path": str(source.relative_to(root)),
        "display_name": source.name,
        "size_gb": 0.01,
        "route": "remux" if not blocked_reason else "",
        "route_reason_code": "h264_direct_stream_safe" if not blocked_reason else "",
        "route_reason": (
            "Fixture source is eligible for the deterministic test-only remux handoff."
            if not blocked_reason
            else ""
        ),
        "blocked_reason_code": blocked_reason_code,
        "blocked_reason": blocked_reason,
        "last_write_utc": _utc_now(),
    }


def _queue_snapshot_payload(fixture: SimpleNamespace, *, completed: bool) -> dict[str, Any]:
    rows = [fixture.blocked_row] if completed else [fixture.runnable_row, fixture.blocked_row]
    return {
        "schema_version": "queue_plan_snapshot.v1",
        "produced_at": _utc_now(),
        "config_path": str(fixture.root / "config.psd1"),
        "local_base": str(fixture.root),
        "source_movies": str(fixture.movies_root),
        "source_tv": str(fixture.tv_root),
        "outsource": str(fixture.output_root),
        "movie_count_total": 0,
        "tv_count_total": 3,
        "priority_count": 0,
        "runnable_count": 0 if completed else 1,
        "total_row_count": len(rows),
        "shown_row_count": len(rows),
        "rows_truncated": False,
        "excluded_count": 1,
        "excluded_row_limit": 100,
        "excluded_rows_truncated": False,
        "excluded_rows": [fixture.excluded_row],
        "rows": rows,
    }


def _write_queue_launch_completed_fixture(root: Path) -> SimpleNamespace:
    tv_root = root / "TV"
    movies_root = root / "Movies"
    output_root = root / "Outsource"
    runnable_source = tv_root / "Runnable Show" / "Season 01" / "Runnable Show S01E01 Ready.mkv"
    blocked_source = tv_root / "Blocked Show" / "Season 01" / "Blocked Show S01E02 Needs Review.mkv"
    excluded_source = tv_root / "Excluded Show" / "Season 01" / "Excluded Show S01E03 Held.mkv"
    for path, payload in (
        (runnable_source, b"queue-runnable-source-fixture"),
        (blocked_source, b"queue-blocked-source-fixture"),
        (excluded_source, b"queue-excluded-source-fixture"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    movies_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    state_root = root / "State"
    queue_snapshot_path = state_root / "Progress" / "queue_snapshot.json"
    progress_path = state_root / "Progress" / "pipeline_progress.json"
    event_file = state_root / "Progress" / "pipeline_events.jsonl"
    completed_manifest_path = state_root / "Completed" / "completed_jobs.jsonl"
    pending_root = root / "PendingServerPush"
    pending_root.mkdir(parents=True, exist_ok=True)
    command_journal_path = state_root / "RunLogs" / "local_api_command_history.json"
    output = output_root / "TV" / "Runnable Show" / "Season 01" / runnable_source.name
    output_sidecar = output.with_name(output.name + ".pipeline.json")

    fixture = SimpleNamespace(
        root=root,
        tv_root=tv_root,
        movies_root=movies_root,
        output_root=output_root,
        state_root=state_root,
        runnable_source=runnable_source,
        blocked_source=blocked_source,
        excluded_source=excluded_source,
        queue_snapshot_path=queue_snapshot_path,
        progress_path=progress_path,
        event_file=event_file,
        completed_manifest_path=completed_manifest_path,
        pending_root=pending_root,
        command_journal_path=command_journal_path,
        output=output,
        output_sidecar=output_sidecar,
    )
    fixture.runnable_row = _queue_row(runnable_source, root=tv_root, order=1)
    fixture.blocked_row = _queue_row(
        blocked_source,
        root=tv_root,
        order=2,
        blocked_reason_code="fixture_operator_review",
        blocked_reason="Fixture row remains blocked for explicit operator review.",
    )
    fixture.excluded_row = {
        "source_order": 3,
        "media_type": "tv",
        "media_kind": "tv",
        "source_path": str(excluded_source),
        "relative_path": str(excluded_source.relative_to(tv_root)),
        "display_name": excluded_source.name,
        "reason_code": "fixture_hold_manifest",
        "reason": "Fixture row remains excluded by backend queue curation.",
    }

    _write_json_atomic(queue_snapshot_path, _queue_snapshot_payload(fixture, completed=False))
    _write_json_atomic(
        progress_path,
        {
            "ProgressVersion": 2,
            "Status": "Completed",
            "CurrentStage": "completed",
            "CurrentQueueIndex": 0,
            "CurrentQueueTotal": 1,
            "TotalProcessed": 0,
            "Remuxed": 0,
            "Encoded": 0,
            "Failed": 0,
            "UpdatedAt": _utc_now(),
        },
    )
    _write_text_atomic(event_file, "")
    _write_text_atomic(completed_manifest_path, "")

    resolved = _resolved(root)
    resolved.local_base = root
    resolved.state_root = state_root
    resolved.source_movies = movies_root
    resolved.source_tv = tv_root
    resolved.outsource = output_root
    resolved.queue_snapshot_path = queue_snapshot_path
    resolved.completed_manifest_path = completed_manifest_path
    resolved.pending_push_path = pending_root
    resolved.event_file = event_file
    resolved.config_data = {
        "NetworkRole": "standalone",
        "SourceMovies": str(movies_root),
        "SourceTV": str(tv_root),
        "Outsource": str(output_root),
        "LocalBase": str(root),
        "RoutingProfile": "plex_direct_stream",
        "SizeGuardMode": "advisory",
        "MinFreeSpaceGB": 0,
        "OutsourceMinFreeSpaceGB": 0,
        "DeferredPublish": False,
    }
    fixture.resolved = resolved
    return fixture


class _StatefulFakeProcess(DummyProc):
    def __init__(self) -> None:
        super().__init__(os.getpid())
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def finish(self, *, outcome: str) -> None:
        self.returncode = 0 if outcome == "completed" else 1
        lease = getattr(self, "_mediapipeline_lifecycle_lease", None)
        if lease is not None:
            lease.release(outcome=outcome)


class _StatefulQueueCompletionService(DummyWorkflowFacadeService):
    def __init__(self, fixture: SimpleNamespace) -> None:
        super().__init__(fixture.root)
        self.fixture = fixture
        self.start_calls: list[dict[str, Any]] = []
        self.fake_processes: list[_StatefulFakeProcess] = []
        self.real_pipeline_child_launch_count = 0
        self.media_tool_invocations: list[str] = []
        self.network_worker_launch_count = 0
        self.started = threading.Event()
        self.completed = threading.Event()
        self.cancel = threading.Event()
        self.runner_failure: BaseException | None = None
        self.runner_thread: threading.Thread | None = None

    def cleanup_stale_launch_guards(self, _resolved_arg: object) -> list[str]:
        return []

    def find_related_pipeline_processes(self, _resolved_arg: object, **_kwargs: object) -> list[object]:
        return []

    def is_progress_stale(self, _progress: dict[str, Any]) -> bool:
        return False

    def is_audit_progress_stale(self, _progress: dict[str, Any]) -> bool:
        return True

    def read_progress(self, _resolved_arg: object) -> dict[str, Any]:
        return json.loads(self.fixture.progress_path.read_text(encoding="utf-8"))

    def read_audit_progress(self, _resolved_arg: object) -> dict[str, Any]:
        return {}

    def build_snapshot(self, resolved: object, audit_root: str) -> Snapshot:
        _ = audit_root
        progress = self.read_progress(resolved)
        active = str(progress.get("CurrentStage") or "").casefold() not in {
            "",
            "completed",
            "idle",
            "stopped",
        }
        events: list[dict[str, Any]] = []
        if self.fixture.event_file.exists():
            for line in self.fixture.event_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    events.append(json.loads(line))
        return Snapshot(
            resolved=resolved,
            current_activity=(
                "Test-only queue completion runner is active."
                if active
                else "Test-only queue completion runner is idle."
            ),
            status_summary="Processing one fixture row." if active else "Fixture queue handoff complete.",
            log_tail="",
            progress=progress,
            audit_progress=None,
            latest_failure_report=None,
            latest_failure_json=None,
            latest_audit_csv=None,
            latest_priority_csv=None,
            pipeline_events=events,
        )

    def start_pipeline(
        self,
        resolved: object,
        mode: str,
        show_config: bool,
        sleep_seconds: int,
        extra_args: str,
        show_console: bool,
        single_file: str | None = None,
        extra_argv: list[str] | tuple[str, ...] | None = None,
    ) -> _StatefulFakeProcess:
        if self.start_calls:
            raise AssertionError("test-only pipeline runner was invoked more than once")
        if mode != "once":
            raise AssertionError(f"test-only pipeline runner expected once mode, got {mode!r}")
        if Path(str(single_file or "")) != self.fixture.runnable_source:
            raise AssertionError(f"test-only pipeline runner received wrong source: {single_file!r}")
        self.start_calls.append(
            {
                "resolved": resolved,
                "mode": mode,
                "show_config": show_config,
                "sleep_seconds": sleep_seconds,
                "extra_args": extra_args,
                "show_console": show_console,
                "single_file": single_file,
                "extra_argv": list(extra_argv or []),
            }
        )
        process = _StatefulFakeProcess()
        self.fake_processes.append(process)
        _write_json_atomic(
            self.fixture.progress_path,
            {
                "ProgressVersion": 2,
                "Status": "Processing",
                "CurrentStage": "remux",
                "CurrentFile": str(self.fixture.runnable_source),
                "CurrentFileDisplay": self.fixture.runnable_source.name,
                "CurrentQueueIndex": 1,
                "CurrentQueueTotal": 1,
                "TotalProcessed": 0,
                "Remuxed": 0,
                "Encoded": 0,
                "Failed": 0,
                "UpdatedAt": _utc_now(),
            },
        )
        self.started.set()
        self.runner_thread = threading.Thread(
            target=self._finish_after_duplicate_is_journaled,
            args=(process,),
            name="QueueLaunchCompletedFakeRunner",
            daemon=True,
        )
        self.runner_thread.start()
        return process

    def _terminal_pipeline_journal_entries(self) -> list[dict[str, Any]]:
        try:
            payload = json.loads(self.fixture.command_journal_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []
        entries = payload.get("entries") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            return []
        return [
            entry
            for entry in entries
            if isinstance(entry, dict)
            and entry.get("command") == "pipeline.start"
            and isinstance(entry.get("data"), dict)
            and entry["data"].get("evidence_phase") in {"completed", "rejected_or_failed"}
        ]

    def _wait_for_duplicate_journal(self) -> None:
        deadline = time.monotonic() + 25.0
        while time.monotonic() < deadline:
            terminal = self._terminal_pipeline_journal_entries()
            if len(terminal) >= 2 and any(entry.get("ok") is True for entry in terminal) and any(
                entry.get("ok") is False for entry in terminal
            ):
                return
            if self.cancel.wait(0.025):
                raise RuntimeError("test-only queue completion runner canceled")
        raise TimeoutError("duplicate pipeline start was not durably journaled before fake completion")

    def _finish_after_duplicate_is_journaled(self, process: _StatefulFakeProcess) -> None:
        try:
            self._wait_for_duplicate_journal()
            self.fixture.output.parent.mkdir(parents=True, exist_ok=True)
            self.fixture.output.write_bytes(b"test-only-completed-output-fixture")
            _write_json_atomic(
                self.fixture.output_sidecar,
                {
                    "schema_version": "pipeline_sidecar.v1",
                    "source_path": str(self.fixture.runnable_source),
                    "output_path": str(self.fixture.output),
                    "route": "remux",
                    "route_reason_code": "h264_direct_stream_safe",
                    "fixture_only": True,
                },
            )
            completed_record = {
                "source_path": str(self.fixture.runnable_source),
                "output_path": str(self.fixture.output),
                "sidecar_path": str(self.fixture.output_sidecar),
                "route": "remux",
                "route_reason": "Deterministic test-only queue handoff.",
                "route_reason_code": "h264_direct_stream_safe",
                "encoder": "copy",
                "audio_summary": "fixture passthrough",
                "subtitle_summary": "fixture originals preserved",
                "source_size": self.fixture.runnable_source.stat().st_size,
                "output_size": self.fixture.output.stat().st_size,
                "encoded_at": _utc_now(),
                "elapsed_seconds": 0,
                "publish_state": "published",
            }
            _write_text_atomic(
                self.fixture.completed_manifest_path,
                json.dumps(completed_record, ensure_ascii=False, sort_keys=True) + "\n",
            )
            _write_json_atomic(
                self.fixture.queue_snapshot_path,
                _queue_snapshot_payload(self.fixture, completed=True),
            )
            event = {
                "schema_version": "pipeline_event.v1",
                "event_id": "fixture-queue-launch-completed",
                "event_type": "job_completed",
                "timestamp": _utc_now(),
                "created_at": _utc_now(),
                "stage": "publish-verification",
                "route": "remux",
                "status": "completed",
                "source_path": str(self.fixture.runnable_source),
                "data": {
                    "success": True,
                    "completion_status": "completed",
                    "queue_terminal": True,
                    "output_path": str(self.fixture.output),
                    "sidecar_path": str(self.fixture.output_sidecar),
                },
            }
            _write_text_atomic(
                self.fixture.event_file,
                json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n",
            )
            _write_json_atomic(
                self.fixture.progress_path,
                {
                    "ProgressVersion": 2,
                    "Status": "Completed",
                    "CurrentStage": "completed",
                    "CurrentFile": "",
                    "CurrentFileDisplay": "",
                    "CurrentQueueIndex": 1,
                    "CurrentQueueTotal": 1,
                    "TotalProcessed": 1,
                    "Remuxed": 1,
                    "Encoded": 0,
                    "Failed": 0,
                    "UpdatedAt": _utc_now(),
                },
            )
            process.finish(outcome="completed")
            self.completed.set()
        except BaseException as exc:  # surfaced by the owning unittest
            self.runner_failure = exc
            try:
                process.finish(outcome="failed")
            finally:
                self.completed.set()

    def stop_fake_runner(self) -> None:
        self.cancel.set()
        thread = self.runner_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)


def _browser_queue_launch_completed_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function queueLaunchCompletedScript() {
          return `
          (async () => {
            const posts = [];
            const api = window.mediaPipelineApi;
            const originalApiPost = api.apiPost;
            api.apiPost = async (path, body, options) => {
              const result = await originalApiPost(path, body, options);
              posts.push({
                path: String(path || ""),
                body: body || {},
                ok: result?.ok === true,
                command: result?.command || "",
                message: result?.message || "",
                evidencePhase: result?.data?.evidence_phase || "",
              });
              return result;
            };
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function tableText(id) { const node = byId(id); return node ? node.innerText || node.textContent || "" : ""; }
            function activePage() { return document.querySelector("[data-page-panel].is-visible")?.dataset.pagePanel || ""; }
            function setInput(id, value) {
              const input = byId(id);
              if (!input) throw new Error("missing input " + id);
              input.value = value;
              input.dispatchEvent(new Event("input", { bubbles: true }));
              input.dispatchEvent(new Event("change", { bubbles: true }));
            }
            async function waitFor(predicate, label, detail = () => "") {
              const deadline = Date.now() + 30000;
              let lastError = null;
              while (Date.now() < deadline) {
                try {
                  if (await predicate()) return;
                } catch (error) {
                  lastError = error;
                }
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error("Timed out waiting for " + label
                + (lastError ? ": " + lastError.message : "")
                + "\\nState:\\n" + detail());
            }
            function clickRow(tbodyId, fragment) {
              const row = Array.from(byId(tbodyId)?.querySelectorAll("tr") || [])
                .find((candidate) => (candidate.innerText || candidate.textContent || "").includes(fragment));
              if (!row) throw new Error(tbodyId + " missing row " + fragment + "\\n" + tableText(tbodyId));
              row.click();
              return row;
            }
            try {
              window.showPage("queue");
              await waitFor(
                () => tableText("queue-rows").includes("Runnable Show S01E01 Ready.mkv")
                  && tableText("queue-rows").includes("Blocked Show S01E02 Needs Review.mkv")
                  && tableText("queue-excluded-rows").includes("Excluded Show S01E03 Held.mkv"),
                "initial runnable, blocked, and excluded Queue rows",
                () => [tableText("queue-rows"), tableText("queue-excluded-rows")].join("\\n\\n"),
              );
              clickRow("queue-rows", "Runnable Show S01E01 Ready.mkv");
              const selected = window.mediaPipelineQueueView.getSelectedQueueRow();
              if (!selected || !String(selected.source_path || "").includes("Runnable Show S01E01 Ready.mkv")) {
                throw new Error("runnable Queue row selection did not become selected-row context: " + JSON.stringify(selected));
              }
              clickRow("queue-launch-decision-rows", "Selected row");
              if (!text("queue-launch-decision-detail").includes("Queue-to-Launch handoff:")) {
                throw new Error("Queue handoff checkpoint detail did not render after selection.");
              }

              window.showPage("launch");
              window.mediaPipelineLaunchView.activateLaunchTab("pipeline", { persist: false });
              const singleFilePreset = document.querySelector('[data-pipeline-scope-preset="single_file"]');
              if (!singleFilePreset) throw new Error("missing Launch Single File scope preset");
              singleFilePreset.click();
              setInput("pipeline-start-mode", "once");
              setInput("pipeline-start-sleep", "1");
              setInput("pipeline-start-schedule-override", "");
              setInput("pipeline-start-single-file", String(selected.source_path || ""));
              await window.mediaPipelineLaunchView.refreshLaunchBackendPreflight();
              window.mediaPipelineLaunchView.updateLaunchCommandButtonStates(
                { pipeline_state: "idle", progress: { Status: "Completed", CurrentStage: "completed" } },
                { safe_to_close: true, active_work: false, state: "completed" },
              );
              await waitFor(
                () => {
                  const button = byId("pipeline-start-button");
                  return Boolean(button && !button.disabled);
                },
                "enabled single-file Start button",
                () => [text("pipeline-start-disabled-reason"), text("launch-backend-preflight-summary")].join("\\n\\n"),
              );
              byId("pipeline-start-button").click();
              await waitFor(
                () => posts.some((post) => post.path === "/api/pipeline/start" && post.ok),
                "successful pipeline start POST",
                () => JSON.stringify(posts),
              );
              const successful = posts.find((post) => post.path === "/api/pipeline/start" && post.ok);
              const duplicate = await originalApiPost("/api/pipeline/start", successful.body);
              posts.push({
                path: "/api/pipeline/start",
                body: successful.body,
                ok: duplicate?.ok === true,
                command: duplicate?.command || "",
                message: duplicate?.message || "",
                evidencePhase: duplicate?.data?.evidence_phase || "",
              });
              if (duplicate?.ok === true) {
                throw new Error("duplicate pipeline start was accepted: " + JSON.stringify(duplicate));
              }
              if (!String(duplicate?.message || "").toLowerCase().includes("lifecycle")) {
                throw new Error("duplicate pipeline start was not rejected by durable lifecycle guard: " + JSON.stringify(duplicate));
              }

              await waitFor(
                async () => {
                  await window.refreshAllNow();
                  window.showPage("queue");
                  const queue = tableText("queue-rows");
                  const excluded = tableText("queue-excluded-rows");
                  window.showPage("completed");
                  const completed = tableText("completed-rows") + "\\n" + tableText("completed-history-rows");
                  return !queue.includes("Runnable Show S01E01 Ready.mkv")
                    && queue.includes("Blocked Show S01E02 Needs Review.mkv")
                    && excluded.includes("Excluded Show S01E03 Held.mkv")
                    && completed.includes("Runnable Show S01E01 Ready.mkv");
                },
                "persisted Queue-to-Completed state transition",
                () => [
                  "page=" + activePage(),
                  "queue=" + tableText("queue-rows"),
                  "excluded=" + tableText("queue-excluded-rows"),
                  "completed=" + tableText("completed-rows"),
                  "completedHistory=" + tableText("completed-history-rows"),
                  "posts=" + JSON.stringify(posts),
                ].join("\\n\\n"),
              );
              const closeReadiness = await window.mediaPipelineApi.apiGet("/api/backend/close-readiness");
              if (closeReadiness?.safe_to_close !== true || closeReadiness?.active_work !== false) {
                throw new Error("backend did not return to safe close readiness: " + JSON.stringify(closeReadiness));
              }
              const queueText = tableText("queue-rows");
              const excludedText = tableText("queue-excluded-rows");
              const completedText = tableText("completed-rows") + "\\n" + tableText("completed-history-rows");
              return {
                posts,
                successful,
                duplicate: {
                  ok: duplicate?.ok === true,
                  command: duplicate?.command || "",
                  message: duplicate?.message || "",
                  evidencePhase: duplicate?.data?.evidence_phase || "",
                },
                queueText,
                excludedText,
                completedText,
                closeReadiness,
              };
            } finally {
              api.apiPost = originalApiPost;
            }
          })()
          `;
        }

        function queueLaunchCompletedReloadScript() {
          return `
          (async () => {
            function byId(id) { return document.getElementById(id); }
            function tableText(id) { const node = byId(id); return node ? node.innerText || node.textContent || "" : ""; }
            async function waitFor(predicate, label) {
              const deadline = Date.now() + 25000;
              while (Date.now() < deadline) {
                if (await predicate()) return;
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error("Timed out waiting for " + label + " after reload\\n"
                + [tableText("queue-rows"), tableText("queue-excluded-rows"), tableText("completed-rows"), tableText("completed-history-rows")].join("\\n\\n"));
            }
            await waitFor(
              () => {
                const queue = tableText("queue-rows");
                const excluded = tableText("queue-excluded-rows");
                const completed = tableText("completed-rows") + "\\n" + tableText("completed-history-rows");
                return !queue.includes("Runnable Show S01E01 Ready.mkv")
                  && queue.includes("Blocked Show S01E02 Needs Review.mkv")
                  && excluded.includes("Excluded Show S01E03 Held.mkv")
                  && completed.includes("Runnable Show S01E01 Ready.mkv");
              },
              "persisted Queue and Completed rows",
            );
            const closeReadiness = await window.mediaPipelineApi.apiGet("/api/backend/close-readiness");
            return {
              queueText: tableText("queue-rows"),
              excludedText: tableText("queue-excluded-rows"),
              completedText: tableText("completed-rows") + "\\n" + tableText("completed-history-rows"),
              closeReadiness,
            };
          })()
          `;
        }

        async function waitForAppReady(client, label) {
          const expression = `Boolean(
            document.readyState === "complete"
            && document.getElementById("queue-rows")
            && document.getElementById("queue-excluded-rows")
            && document.getElementById("completed-rows")
            && document.getElementById("pipeline-start-button")?.dataset.pipelineStartBound === "true"
            && typeof window.showPage === "function"
            && typeof window.refreshAllNow === "function"
            && typeof window.mediaPipelineApi?.apiPost === "function"
            && typeof window.mediaPipelineApi?.apiGet === "function"
            && typeof window.mediaPipelineQueueView?.getSelectedQueueRow === "function"
            && typeof window.mediaPipelineLaunchView?.refreshLaunchBackendPreflight === "function"
          )`;
          const deadline = Date.now() + 25000;
          while (Date.now() < deadline) {
            const ready = await client.send("Runtime.evaluate", { expression, returnByValue: true });
            if (ready.result?.value === true) return;
            await sleep(100);
          }
          throw new Error("WebView did not become ready for " + label);
        }

        async function evaluate(client, expression) {
          const result = await client.send("Runtime.evaluate", {
            expression,
            awaitPromise: true,
            returnByValue: true,
          });
          if (result.exceptionDetails) {
            const details = result.exceptionDetails;
            throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
          }
          return result.result?.value || {};
        }

        async function main() {
          const userDataDir = fs.mkdtempSync(`${payload.tmpRoot.replace(/\\/g, "/")}/chrome-profile-`);
          const browser = launchBrowser([
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-sync",
            "--metrics-recording-only",
            "--no-first-run",
            "--no-default-browser-check",
            `--remote-debugging-port=${payload.port}`,
            `--user-data-dir=${userDataDir}`,
            payload.url,
          ]);
          let client = null;
          try {
            const wsUrl = await waitForPageWebSocket(payload.port, payload.url);
            client = createCdpClient(wsUrl);
            await client.send("Runtime.enable");
            await client.send("Log.enable");
            await client.send("Page.enable");
            await waitForAppReady(client, "initial workflow");
            const workflow = await evaluate(client, queueLaunchCompletedScript());
            await client.send("Page.reload", { ignoreCache: true });
            await waitForAppReady(client, "persisted reload");
            const reload = await evaluate(client, queueLaunchCompletedReloadScript());
            const errorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || errorEvents.length) {
              throw new Error(`Browser console/exception noise: ${client.exceptions.concat(errorEvents).join("; ")}`);
            }
            console.log(JSON.stringify({ ok: true, result: { workflow, reload } }));
          } finally {
            if (client) client.close();
            await terminateBrowser(browser);
          }
        }

        main().catch((error) => {
          console.error(error.stack || error.message || String(error));
          process.exit(1);
        });
        """
    )


def _run_browser_queue_launch_completed_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed Queue-to-Completed smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        payload_path = tmp / "browser-queue-launch-completed-payload.json"
        runner_path = tmp / "browser-queue-launch-completed-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": _free_port(),
                    "tmpRoot": str(tmp),
                    "url": url,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_queue_launch_completed_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed Queue -> Launch -> Completed stateful smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=100,
        )


class WebViewBrowserQueueLaunchCompletedSmoke(unittest.TestCase):
    def test_real_browser_moves_only_runnable_queue_row_to_completed(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed Queue-to-Completed smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            fixture = _write_queue_launch_completed_fixture(Path(raw_root))
            source_snapshot = capture_media_no_mutation_snapshot(fixture.tv_root)
            service = _StatefulQueueCompletionService(fixture)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            facade._autonomy_health_for_resolved = lambda _resolved_arg, **_kwargs: {  # type: ignore[method-assign]
                "overall_status": "ready"
            }
            server = LocalApiServer(
                facade,
                token="browser-queue-launch-completed-token",
                resolved_provider=lambda: fixture.resolved,
                snapshot_provider=lambda: service.build_snapshot(fixture.resolved, str(fixture.root)),
                audit_root_provider=lambda: str(fixture.root),
                command_journal_path=fixture.command_journal_path,
            )
            try:
                server.start()
                result = _run_browser_queue_launch_completed_smoke(browser_path=browser_path, url=server.url)
            finally:
                service.stop_fake_runner()
                server.stop()

            self.assertTrue(result["ok"])
            self.assertIsNone(service.runner_failure)
            self.assertTrue(service.started.is_set())
            self.assertTrue(service.completed.is_set())
            self.assertEqual(len(service.start_calls), 1)
            self.assertEqual(service.start_calls[0]["mode"], "once")
            self.assertEqual(Path(str(service.start_calls[0]["single_file"])), fixture.runnable_source)
            self.assertEqual(len(service.fake_processes), 1)
            self.assertEqual(service.fake_processes[0].returncode, 0)
            self.assertEqual(service.real_pipeline_child_launch_count, 0)
            self.assertEqual(service.media_tool_invocations, [])
            self.assertEqual(service.network_worker_launch_count, 0)

            browser_result = result["result"]
            workflow = browser_result["workflow"]
            reload_result = browser_result["reload"]
            pipeline_posts = [post for post in workflow["posts"] if post["path"] == "/api/pipeline/start"]
            self.assertEqual(len(pipeline_posts), 2)
            self.assertEqual(sum(1 for post in pipeline_posts if post["ok"]), 1)
            self.assertEqual(workflow["successful"]["body"]["mode"], "once")
            self.assertEqual(
                Path(str(workflow["successful"]["body"]["single_file"])),
                fixture.runnable_source,
            )
            self.assertFalse(workflow["duplicate"]["ok"])
            self.assertIn("lifecycle", workflow["duplicate"]["message"].casefold())
            for state in (workflow, reload_result):
                self.assertNotIn(fixture.runnable_source.name, state["queueText"])
                self.assertIn(fixture.blocked_source.name, state["queueText"])
                self.assertIn(fixture.excluded_source.name, state["excludedText"])
                self.assertIn(fixture.runnable_source.name, state["completedText"])
                self.assertTrue(state["closeReadiness"]["safe_to_close"])
                self.assertFalse(state["closeReadiness"]["active_work"])

            journal = json.loads(fixture.command_journal_path.read_text(encoding="utf-8"))
            pipeline_entries = [entry for entry in journal["entries"] if entry.get("command") == "pipeline.start"]
            self.assertEqual(len(pipeline_entries), 4)
            accepted = [entry for entry in pipeline_entries if entry.get("data", {}).get("evidence_phase") == "accepted"]
            terminal = [
                entry
                for entry in pipeline_entries
                if entry.get("data", {}).get("evidence_phase") in {"completed", "rejected_or_failed"}
            ]
            self.assertEqual(len(accepted), 2)
            self.assertEqual(len(terminal), 2)
            self.assertEqual(sum(1 for entry in terminal if entry.get("ok") is True), 1)
            self.assertEqual(sum(1 for entry in terminal if entry.get("ok") is False), 1)

            queue_snapshot = json.loads(fixture.queue_snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(queue_snapshot["runnable_count"], 0)
            self.assertEqual([row["source_path"] for row in queue_snapshot["rows"]], [str(fixture.blocked_source)])
            self.assertEqual(
                [row["source_path"] for row in queue_snapshot["excluded_rows"]],
                [str(fixture.excluded_source)],
            )
            completed_lines = fixture.completed_manifest_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(completed_lines), 1)
            completed_record = json.loads(completed_lines[0])
            self.assertEqual(completed_record["source_path"], str(fixture.runnable_source))
            self.assertEqual(completed_record["output_path"], str(fixture.output))
            self.assertEqual(completed_record["sidecar_path"], str(fixture.output_sidecar))
            self.assertTrue(fixture.output.is_file())
            sidecar = json.loads(fixture.output_sidecar.read_text(encoding="utf-8"))
            self.assertEqual(sidecar["schema_version"], "pipeline_sidecar.v1")
            self.assertEqual(sidecar["source_path"], str(fixture.runnable_source))
            self.assertEqual(
                json.loads(fixture.progress_path.read_text(encoding="utf-8"))["CurrentStage"],
                "completed",
            )
            self.assertEqual(LifecycleLeaseStore(fixture.state_root).status()["status"], "idle")
            self.assertEqual(list(fixture.pending_root.iterdir()), [])
            self.assertFalse((fixture.state_root / "Network").exists())
            assert_media_no_mutation(self, source_snapshot)


if __name__ == "__main__":
    unittest.main()
