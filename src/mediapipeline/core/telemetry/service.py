from __future__ import annotations

from collections.abc import Callable
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

try:
    import psutil
except Exception:  # pragma: no cover - optional runtime dependency
    psutil = None

from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.telemetry.contracts import TelemetrySnapshot
from mediapipeline.core.telemetry.health import (
    api_contract_health_rows,
    ass_to_srt_exception_row,
    ass_to_srt_missing_row,
    ass_to_srt_result_row,
    bundle_layout_health_rows,
    bundled_tool_health_rows,
    config_schema_health_rows,
    configured_root_health_rows,
    find_ass_to_srt_script,
    library_output_health_rows,
    nvidia_smi_health_row,
    process_guard_health_rows,
    powershell_health_row,
    runtime_state_health_rows,
    subtitle_tool_health_rows,
)
from mediapipeline.core.telemetry.nvidia import apply_nvidia_smi_rows_to_snapshot, parse_nvidia_smi_encoder_rows
from mediapipeline.core.telemetry.system_metrics import (
    apply_system_metrics_to_snapshot,
    create_cpu_sampler,
    create_cpu_utility_sampler,
    prime_cpu_sampler,
)
from mediapipeline.core.kernel.runtime.subprocess_runner import run_capture


# Background sampling cadence for the cached CPU/memory telemetry snapshot. The
# WebView's automatic refresh runs every 15s (app.js AUTOMATIC_REFRESH_INTERVAL_MS),
# so a 2s sampler keeps each UI fetch reading a CPU/mem value at most ~2s old and
# lets CPU drops (e.g. a finished encode) clear quickly instead of lingering on a
# busy tail. CPU/mem sampling is cheap (PDH counter + psutil), so this stays low.
TELEMETRY_INTERVAL_SECONDS = 2.0

# GPU telemetry sub-cadence. Unlike CPU/mem, each GPU read spawns an nvidia-smi
# process (NVML driver query plus Windows process-creation/AV-scan cost), so
# probing every 2s is a periodic system-load source that contends with other
# workloads (e.g. an editor/agent reindexing the disk). Probe at most this often
# and reuse the last parsed rows on intermediate cycles; kept just under the 15s
# UI refresh so each UI fetch still sees recent GPU data.
GPU_TELEMETRY_INTERVAL_SECONDS = 12.0


class TelemetryServiceMixin:
    def _initialize_telemetry_sampler(self) -> None:
        self._cpu_sampler = create_cpu_sampler()
        self._cpu_utility_sampler = create_cpu_utility_sampler()
        prime_cpu_sampler(psutil, self._cpu_sampler, self._cpu_utility_sampler)
        # GPU probe sub-cadence cache (see GPU_TELEMETRY_INTERVAL_SECONDS): the
        # last parsed nvidia-smi rows and the monotonic time of the last probe.
        self._last_gpu_rows: list | None = None
        self._last_gpu_sample_at: float | None = None

    def _resolve_nvidia_smi(self) -> str | None:
        if self._nvidia_smi_checked:
            return self._nvidia_smi_path

        candidates = [
            shutil.which("nvidia-smi.exe"),
            shutil.which("nvidia-smi"),
            r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
        ]
        self._nvidia_smi_checked = True
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                self._nvidia_smi_path = str(candidate)
                break
        return self._nvidia_smi_path

    def start_background_tasks(self) -> None:
        if self._telemetry_thread and self._telemetry_thread.is_alive():
            return
        self._telemetry_stop.clear()
        self._telemetry_thread = threading.Thread(
            target=self._telemetry_loop,
            name="MediaPipelineTelemetry",
            daemon=True,
        )
        self._telemetry_thread.start()

    def stop_background_tasks(self) -> None:
        self._telemetry_stop.set()
        thread = self._telemetry_thread
        if thread and thread.is_alive():
            thread.join(timeout=1.5)
        self._telemetry_thread = None

    def _telemetry_loop(self) -> None:
        while not self._telemetry_stop.is_set():
            snapshot = self.sample_system_telemetry()
            with self._telemetry_lock:
                self._cached_telemetry = snapshot
            self._telemetry_stop.wait(TELEMETRY_INTERVAL_SECONDS)

    def get_cached_telemetry(self) -> TelemetrySnapshot:
        with self._telemetry_lock:
            return self._cached_telemetry

    def sample_system_telemetry(self, now: float | None = None) -> TelemetrySnapshot:
        snapshot = TelemetrySnapshot(collected_at=datetime.now())

        apply_system_metrics_to_snapshot(
            snapshot,
            psutil,
            getattr(self, "_cpu_sampler", None),
            getattr(self, "_cpu_utility_sampler", None),
        )

        self._apply_gpu_telemetry(
            snapshot,
            now=time.monotonic() if now is None else float(now),
        )
        return snapshot

    def _apply_gpu_telemetry(self, snapshot: TelemetrySnapshot, *, now: float) -> None:
        """Attach GPU telemetry to ``snapshot``.

        Unlike CPU/mem, each reading spawns an ``nvidia-smi`` process, so this
        probes at most every ``GPU_TELEMETRY_INTERVAL_SECONDS`` and reuses the
        last parsed rows on intermediate cycles. This is the only telemetry path
        that spawns a process; gating it keeps the 2s sampler from generating a
        steady nvidia-smi spawn storm that contends with other system workloads.
        """
        nvidia_smi = self._resolve_nvidia_smi()
        if not nvidia_smi:
            return

        last_sample_at = getattr(self, "_last_gpu_sample_at", None)
        if last_sample_at is not None and (now - last_sample_at) < GPU_TELEMETRY_INTERVAL_SECONDS:
            cached_rows = getattr(self, "_last_gpu_rows", None)
            if cached_rows:
                apply_nvidia_smi_rows_to_snapshot(snapshot, cached_rows)
            return

        # Due for a fresh probe. Advance the timer up front so a persistently
        # failing nvidia-smi cannot fall back to spawning a process every cycle.
        self._last_gpu_sample_at = now
        try:
            result = run_capture(
                [
                    nvidia_smi,
                    "--query-gpu=index,name,utilization.encoder,utilization.gpu,temperature.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                encoding="utf-8",
                errors="replace",
                timeout_seconds=2,
                extra_popen_kwargs=self._subprocess_kwargs_hidden(),
                label="nvidia-smi telemetry",
            )
            output = result.stdout.strip()
            if result.timed_out and not snapshot.error:
                snapshot.error = f"nvidia-smi timed out: {result.kill_message}"
            elif result.returncode == 0 and output:
                gpu_rows, parse_failures = parse_nvidia_smi_encoder_rows(output)
                if gpu_rows:
                    apply_nvidia_smi_rows_to_snapshot(snapshot, gpu_rows)
                    self._last_gpu_rows = gpu_rows
                elif parse_failures and not snapshot.error:
                    snapshot.error = "nvidia-smi returned malformed encoder telemetry"
                elif not snapshot.error:
                    snapshot.error = "nvidia-smi returned no parseable encoder telemetry"
            elif not snapshot.error and result.stderr.strip():
                snapshot.error = result.stderr.strip()
            elif not snapshot.error and result.returncode not in (0, None):
                snapshot.error = f"nvidia-smi exited with code {result.returncode}"
        except Exception as exc:
            if not snapshot.error:
                snapshot.error = f"nvidia-smi error: {exc}"

    def check_environment_health(
        self,
        resolved: ResolvedPaths,
        *,
        progress_callback: Callable[[dict[str, object]], None] | None = None,
    ) -> list[tuple[str, bool, str]]:
        results: list[tuple[str, bool, str]] = []

        def emit(active_step_id: str, active_detail: str = "") -> None:
            if callable(progress_callback):
                progress_callback(
                    {
                        "active_step_id": active_step_id,
                        "active_detail": active_detail,
                        "rows": list(results),
                    }
                )

        emit("config_parse", "Checking active config schema.")
        results.extend(config_schema_health_rows(resolved))
        emit("path_reachability", "Checking configured source/scratch/output roots.")
        results.extend(configured_root_health_rows(resolved))
        results.extend(library_output_health_rows(resolved))
        emit("state_directory", "Checking runtime state files.")
        results.extend(runtime_state_health_rows(resolved))
        emit("api_contract", "Checking backend API contract surfaces.")
        results.extend(api_contract_health_rows())
        emit("process_guard", "Checking process and ActiveJobs safety posture.")
        results.extend(process_guard_health_rows(resolved, self))
        emit("bundle_layout", "Checking bundle and launcher layout.")
        results.extend(bundle_layout_health_rows(resolved.workspace_root, resolved.app_root))
        emit("powershell", "Checking PowerShell host.")
        results.append(
            powershell_health_row(
                resolved.powershell_host,
                run_capture_func=run_capture,
                extra_popen_kwargs=self._subprocess_kwargs_hidden(),
            )
        )
        emit("ffmpeg", "Checking bundled or system FFmpeg.")
        for row in bundled_tool_health_rows(
            self.workspace_root,
            self.app_root,
            config=getattr(resolved, "config_data", {}),
            run_capture_func=run_capture,
            extra_popen_kwargs=self._subprocess_kwargs_hidden(),
        ):
            results.append(row)
            name = str(row[0]).casefold()
            if "ffmpeg" in name:
                emit("ffprobe", "Checking bundled or system ffprobe.")
            elif "ffprobe" in name:
                emit("mkvtoolnix", "Checking bundled or system MKVToolNix.")
            elif "mkvmerge" in name or "mkvtool" in name:
                emit("mkvextract", "Checking bundled or system mkvextract.")
            elif "mkvextract" in name:
                emit("gpu_telemetry", "Checking optional GPU telemetry.")
        results.append(nvidia_smi_health_row(self._resolve_nvidia_smi()))

        script_path = find_ass_to_srt_script(resolved.workspace_root, resolved.app_root)
        if not script_path:
            results.append(ass_to_srt_missing_row())
        else:
            try:
                emit("subtitle_helper", "Running subtitle helper import/argument probe.")
                r = run_capture(
                    [sys.executable, str(script_path)],
                    timeout_seconds=15,
                    extra_popen_kwargs=self._subprocess_kwargs_hidden(),
                    label="ass_to_srt environment check",
                )
                results.append(ass_to_srt_result_row(script_path, r.returncode, r.stderr))
            except Exception as exc:
                results.append(ass_to_srt_exception_row(exc))

        emit("subtitle_bdpgs_ocr", "Checking BDPGS OCR helper paths.")
        for row in subtitle_tool_health_rows(
            resolved.workspace_root,
            resolved.app_root,
            getattr(resolved, "config_data", {}),
            run_capture_func=run_capture,
            extra_popen_kwargs=self._subprocess_kwargs_hidden(),
        ):
            results.append(row)
            name = str(row[0]).casefold()
            if "tessdata" in name or "bdpgs" in name:
                emit("subtitle_vobsub_ocr", "Checking VobSub OCR helper paths.")
        emit("pending_publish_path", "Checking pending-publish path posture.")

        return results
