from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from mediapipeline.core.config.library_profiles import effective_library_profiles_from_config
from mediapipeline.contracts.config import Config
from mediapipeline.core.kernel.config_keys import (
    KEY_FINAL_LIBRARY_PROMOTION_ENABLED,
    KEY_FINAL_LIBRARY_PROMOTION_RULES,
    KEY_LOCAL_BASE,
    KEY_OUTSOURCE,
    KEY_SOURCE_MOVIES,
    KEY_SOURCE_TV,
)
from mediapipeline.core.storage.db import STATE_DB_FILENAME

HealthRow = tuple[str, bool, str]

SUBTITLE_LANGUAGE_MAP = {
    "eng": "eng",
    "en": "eng",
    "und": "eng",
    "": "eng",
    "jpn": "jpn",
    "ja": "jpn",
    "spa": "spa",
    "es": "spa",
    "fre": "fra",
    "fra": "fra",
    "fr": "fra",
    "ger": "deu",
    "deu": "deu",
    "de": "deu",
    "ita": "ita",
    "it": "ita",
    "por": "por",
    "pt": "por",
    "rus": "rus",
    "ru": "rus",
    "chi": "chi_sim",
    "zho": "chi_sim",
    "zh": "chi_sim",
    "kor": "kor",
    "ko": "kor",
}

BDPGS_OCR_TOOL_DEFAULT = r"Tools\PgsToSrt\PgsToSrt.exe"
BDPGS_OCR_TESSDATA_DEFAULT = r"Tools\PgsToSrt\tessdata"
VOBSUB_OCR_TOOL_DEFAULT = r"Tools\SubtitleEditLegacy\SubtitleEdit.exe"
DEFAULT_SUBTITLE_OCR_LANGUAGES = ("eng", "en", "und")

VOBSUB_TESSERACT_CANDIDATES = (
    r"Tools\SubtitleEditLegacy\Tesseract550\tesseract.exe",
    r"Tools\SubtitleEditLegacy\Tesseract-OCR\tesseract.exe",
    r"Tools\SubtitleEditLegacy\Tesseract302\tesseract.exe",
    r"Tools\SubtitleEditLegacy\Tesseract\tesseract.exe",
    r"Tools\SubtitleEdit\Tesseract550\tesseract.exe",
    r"Tools\SubtitleEdit\Tesseract-OCR\tesseract.exe",
    r"Tools\SubtitleEdit\Tesseract\tesseract.exe",
    r"Tools\Tesseract-OCR\tesseract.exe",
    r"Tools\Tesseract\tesseract.exe",
)

TOOL_HEALTH_DEFINITIONS = (
    (
        "ffmpeg",
        "ffmpeg.exe",
        "ffmpeg",
        (
            "ops/pipeline/tools/ffmpeg/bin/ffmpeg.exe",
            "ops/pipeline/tools/ffmpeg/bin/ffmpeg",
        ),
    ),
    (
        "ffprobe",
        "ffprobe.exe",
        "ffprobe",
        (
            "ops/pipeline/tools/ffmpeg/bin/ffprobe.exe",
            "ops/pipeline/tools/ffmpeg/bin/ffprobe",
        ),
    ),
    (
        "mkvmerge",
        "mkvmerge.exe",
        "mkvmerge",
        (
            "ops/pipeline/tools/MKVToolNix/mkvmerge.exe",
            "ops/pipeline/tools/MKVToolNix/mkvmerge",
        ),
    ),
    (
        "mkvextract",
        "mkvextract.exe",
        "mkvextract",
        (
            "ops/pipeline/tools/MKVToolNix/mkvextract.exe",
            "ops/pipeline/tools/MKVToolNix/mkvextract",
        ),
    ),
)

TOOL_VERSION_ARGS = {
    "ffmpeg": ("-hide_banner", "-version"),
    "ffprobe": ("-hide_banner", "-version"),
    "mkvmerge": ("--version",),
    "mkvextract": ("--version",),
}

REMOVED_ROOT_LAUNCHERS = (
    "Start-MediaPipelineRemuxEncodeAIO-LocalApi.bat",
    "Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat",
    "Run-MediaPipelineRemuxEncodeAIO.bat",
    "Setup-MediaPipelineRemuxEncodeAIO.bat",
    "Verify-MediaPipelineRemuxEncodeAIO-Environment.bat",
    "Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1",
    "Build-MediaPipelineRemuxEncodeAIO-Release.ps1",
    "Test-MediaPipelineRemuxEncodeAIO-Release.ps1",
    "New-RealMediaValidationWorksheet.ps1",
)

CANONICAL_LAYOUT_PATHS = (
    ("ops/scripts/dev/start-local-api.bat", "canonical Local API launcher"),
    ("ops/scripts/dev/start-tauri-preview.bat", "canonical Tauri preview launcher"),
    ("ops/scripts/dev/start-api-and-browser.bat", "canonical API/browser launcher"),
    ("ops/scripts/dev/run.bat", "canonical operator launcher"),
    ("ops/scripts/dev/verify-env.bat", "canonical environment verifier"),
    ("ops/scripts/dev/verify-env.ps1", "canonical environment verifier"),
    ("apps/desktop/runtime/Python/python.exe", "bundled Python runtime"),
    ("ops/pipeline/runtime/PowerShell-7.6.0-win-x64/pwsh.exe", "bundled PowerShell runtime"),
    ("apps/desktop/webview/static/index.html", "backend-served WebView index"),
)

RUNTIME_STATE_FILE_ATTRS = (
    "app_state_path",
    "progress_file",
    "event_file",
    "queue_snapshot_path",
    "completed_manifest_path",
    "priority_manifest_path",
    "queue_strategy_path",
    "file_overrides_path",
    "audit_score_policy_path",
    "audit_ignore_manifest_path",
)

REQUIRED_API_CONTRACT_ROUTES = (
    "/api/health",
    "/api/contract",
    "/api/snapshot",
    "/api/maintenance",
    "/api/maintenance/progress",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().casefold()
    if not text:
        return default
    if text in {"1", "true", "yes", "on", "enabled", "enable"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", "disable"}:
        return False
    return default


def _output_snippet(stdout: str, stderr: str, *, fallback: str = "") -> str:
    text = (stdout or stderr or fallback or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:180]


def _probe_command(
    args: list[str],
    *,
    run_capture_func: Callable[..., Any] | None,
    timeout_seconds: int,
    extra_popen_kwargs: dict[str, Any] | None = None,
    label: str = "health probe",
    accepted_returncodes: Iterable[int] = (0,),
) -> tuple[bool, str]:
    if run_capture_func is None:
        return True, ""
    try:
        result = run_capture_func(
            args,
            timeout_seconds=timeout_seconds,
            encoding="utf-8",
            errors="replace",
            extra_popen_kwargs=extra_popen_kwargs or {},
            label=label,
        )
    except Exception as exc:
        return False, str(exc)
    if bool(getattr(result, "timed_out", False)):
        return False, str(getattr(result, "kill_message", "") or f"timed out after {timeout_seconds}s")
    returncode = int(getattr(result, "returncode", 1) or 0)
    snippet = _output_snippet(
        str(getattr(result, "stdout", "") or ""),
        str(getattr(result, "stderr", "") or ""),
        fallback=f"exit {returncode}",
    )
    if returncode in {int(code) for code in accepted_returncodes}:
        return True, snippet
    return False, snippet or f"exit {returncode}"


def _probe_command_with_output(
    args: list[str],
    *,
    run_capture_func: Callable[..., Any] | None,
    timeout_seconds: int,
    extra_popen_kwargs: dict[str, Any] | None = None,
    label: str = "health probe",
    accepted_returncodes: Iterable[int] = (0,),
) -> tuple[bool, str, str]:
    if run_capture_func is None:
        return True, "", ""
    try:
        result = run_capture_func(
            args,
            timeout_seconds=timeout_seconds,
            encoding="utf-8",
            errors="replace",
            extra_popen_kwargs=extra_popen_kwargs or {},
            label=label,
        )
    except Exception as exc:
        return False, str(exc), ""
    if bool(getattr(result, "timed_out", False)):
        detail = str(getattr(result, "kill_message", "") or f"timed out after {timeout_seconds}s")
        return False, detail, ""
    returncode = int(getattr(result, "returncode", 1) or 0)
    stdout = str(getattr(result, "stdout", "") or "")
    stderr = str(getattr(result, "stderr", "") or "")
    combined = f"{stdout}\n{stderr}".strip()
    snippet = _output_snippet(stdout, stderr, fallback=f"exit {returncode}")
    if returncode in {int(code) for code in accepted_returncodes}:
        return True, snippet, combined
    return False, snippet or f"exit {returncode}", combined


def _append_probe_detail(path: str | Path, ok: bool, probe_detail: str) -> str:
    if not probe_detail:
        return str(path)
    status = "probe ok" if ok else "probe failed"
    return f"{path}; {status}: {probe_detail}"


def powershell_health_row(
    pwsh: str | None,
    *,
    run_capture_func: Callable[..., Any] | None = None,
    extra_popen_kwargs: dict[str, Any] | None = None,
) -> HealthRow:
    if pwsh:
        ok, detail = _probe_command(
            [
                pwsh,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "$PSVersionTable.PSVersion.ToString()",
            ],
            run_capture_func=run_capture_func,
            timeout_seconds=8,
            extra_popen_kwargs=extra_popen_kwargs,
            label="PowerShell health probe",
        )
        return ("PowerShell (pwsh)", ok, _append_probe_detail(pwsh, ok, detail))
    return ("PowerShell (pwsh)", False, "Not found in bundled path or system PATH")


def find_bundled_or_system_tool(
    workspace_root: Path,
    app_root: Path,
    win_name: str,
    unix_name: str,
    rel_paths: Iterable[str],
    *,
    which: Callable[[str], str | None] = shutil.which,
) -> str | None:
    for rel in rel_paths:
        for base in (workspace_root, app_root):
            candidate = base / rel
            if candidate.exists():
                return str(candidate)
    return which(win_name) or which(unix_name)


def bundled_tool_health_rows(
    workspace_root: Path,
    app_root: Path,
    *,
    which: Callable[[str], str | None] = shutil.which,
    config: Mapping[str, Any] | None = None,
    run_capture_func: Callable[..., Any] | None = None,
    extra_popen_kwargs: dict[str, Any] | None = None,
) -> list[HealthRow]:
    results: list[HealthRow] = []
    for tool_name, win_name, unix_name, rel_paths in TOOL_HEALTH_DEFINITIONS:
        found = find_bundled_or_system_tool(
            workspace_root,
            app_root,
            win_name,
            unix_name,
            rel_paths,
            which=which,
        )
        if found:
            ok, detail = tool_capability_detail(
                tool_name,
                found,
                config=config,
                run_capture_func=run_capture_func,
                extra_popen_kwargs=extra_popen_kwargs,
            )
            results.append((tool_name, ok, detail))
        else:
            results.append((tool_name, False, "Not found in bundled Tools or system PATH"))
    return results


def tool_capability_detail(
    tool_name: str,
    tool_path: str,
    *,
    config: Mapping[str, Any] | None = None,
    run_capture_func: Callable[..., Any] | None = None,
    extra_popen_kwargs: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    if run_capture_func is None:
        return True, tool_path
    version_args = TOOL_VERSION_ARGS.get(tool_name, ("--version",))
    ok, probe_detail = _probe_command(
        [tool_path, *version_args],
        run_capture_func=run_capture_func,
        timeout_seconds=10,
        extra_popen_kwargs=extra_popen_kwargs,
        label=f"{tool_name} version health probe",
    )
    if not ok:
        return False, _append_probe_detail(tool_path, ok, probe_detail)

    if tool_name != "ffmpeg":
        return True, _append_probe_detail(tool_path, ok, probe_detail)

    encoders_ok, encoders_detail, encoders_output = _probe_command_with_output(
        [tool_path, "-hide_banner", "-encoders"],
        run_capture_func=run_capture_func,
        timeout_seconds=12,
        extra_popen_kwargs=extra_popen_kwargs,
        label="ffmpeg encoder inventory health probe",
    )
    if not encoders_ok:
        return False, f"{tool_path}; version ok; encoder inventory failed: {encoders_detail}"
    selected_encoder = _text((config or {}).get("VideoCodec"))
    if selected_encoder and selected_encoder.casefold() not in encoders_output.casefold():
        return False, f"{tool_path}; encoder inventory listed, but selected VideoCodec '{selected_encoder}' was not visible"
    encoder_text = f"; selected encoder {selected_encoder} visible" if selected_encoder else ""
    return True, f"{tool_path}; version ok; encoder inventory listed{encoder_text}"


def health_config_bool(config: object, key: str, default: bool = False) -> bool:
    if not isinstance(config, dict):
        return default
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().casefold()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off", ""}:
        return False
    return default


def health_config_text(config: object, key: str, default: str = "") -> str:
    if not isinstance(config, dict) or key not in config:
        return default
    value = config.get(key)
    return str(value or "").strip()


def health_config_languages(config: object, key: str) -> list[str]:
    if not isinstance(config, dict):
        values: Iterable[object] = DEFAULT_SUBTITLE_OCR_LANGUAGES
    else:
        raw = config.get(key, DEFAULT_SUBTITLE_OCR_LANGUAGES)
        if isinstance(raw, (list, tuple, set)):
            values = raw
        elif isinstance(raw, str):
            values = [part.strip() for part in raw.split(",")]
        else:
            values = DEFAULT_SUBTITLE_OCR_LANGUAGES
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip().casefold()
        mapped = SUBTITLE_LANGUAGE_MAP.get(text, text)
        if mapped and mapped not in normalized:
            normalized.append(mapped)
    return normalized or ["eng"]


def health_path_roots(workspace_root: Path, app_root: Path) -> list[Path]:
    candidates = [
        workspace_root / "ops" / "pipeline",
        workspace_root / "ops" / "pipeline" / "tools",
        app_root / "pipeline",
        app_root / "tools",
        workspace_root,
        app_root,
    ]
    roots: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).casefold()
        if key not in seen:
            roots.append(candidate)
            seen.add(key)
    return roots


def resolve_health_path(
    workspace_root: Path,
    app_root: Path,
    path_text: str,
    *,
    path_type: str,
) -> Path | None:
    text = str(path_text or "").strip()
    if not text:
        return None
    raw = Path(text)
    candidates = [raw] if raw.is_absolute() else [base / raw for base in health_path_roots(workspace_root, app_root)]
    for candidate in candidates:
        try:
            if path_type == "directory" and candidate.is_dir():
                return candidate.resolve()
            if path_type == "file" and candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    return None


def subtitle_health_label(label: str, required: bool) -> str:
    return label if required else f"{label} (optional)"


def subtitle_config_file_health_row(
    workspace_root: Path,
    app_root: Path,
    label: str,
    configured_value: str,
    *,
    required: bool,
    allow_system_tools: bool,
    which_names: Iterable[str],
    which: Callable[[str], str | None] = shutil.which,
    unsupported_leaf_names: Iterable[str] = (),
    missing_detail: str = "",
    run_capture_func: Callable[..., Any] | None = None,
    extra_popen_kwargs: dict[str, Any] | None = None,
    probe_args: Iterable[str] = (),
    accepted_probe_returncodes: Iterable[int] = (0,),
) -> HealthRow:
    display_label = subtitle_health_label(label, required)
    configured = str(configured_value or "").strip()
    if not configured:
        return (display_label, False, missing_detail or "Path is not configured.")

    resolved = resolve_health_path(workspace_root, app_root, configured, path_type="file")
    if resolved is None and allow_system_tools:
        for name in which_names:
            found = which(name)
            if found:
                resolved = Path(found)
                break
    if resolved is None:
        return (display_label, False, missing_detail or f"Not found: {configured}")

    leaf = resolved.name.casefold()
    if leaf in {name.casefold() for name in unsupported_leaf_names}:
        return (display_label, False, f"{resolved} is not supported for this OCR path")

    if resolved.suffix.casefold() == ".dll":
        dotnet = which("dotnet")
        if not dotnet:
            return (display_label, False, f"{resolved} is a .dll but dotnet was not found on PATH")
        return (display_label, True, f"{dotnet} {resolved}")

    if run_capture_func is not None and tuple(probe_args):
        ok, detail = _probe_command(
            [str(resolved), *[str(arg) for arg in probe_args]],
            run_capture_func=run_capture_func,
            timeout_seconds=12,
            extra_popen_kwargs=extra_popen_kwargs,
            label=f"{label} health probe",
            accepted_returncodes=accepted_probe_returncodes,
        )
        return (display_label, ok, _append_probe_detail(resolved, ok, detail))

    return (display_label, True, str(resolved))


def subtitle_config_directory_health_row(
    workspace_root: Path,
    app_root: Path,
    label: str,
    configured_value: str,
    *,
    required: bool,
    expected_languages: Iterable[str],
    blank_ok_detail: str = "",
    missing_detail: str = "",
) -> HealthRow:
    display_label = subtitle_health_label(label, required)
    configured = str(configured_value or "").strip()
    if not configured:
        if blank_ok_detail:
            return (display_label, True, blank_ok_detail)
        return (display_label, False, missing_detail or "Path is not configured.")

    resolved = resolve_health_path(workspace_root, app_root, configured, path_type="directory")
    if resolved is None:
        return (display_label, False, missing_detail or f"Directory not found: {configured}")

    missing_languages = [
        language for language in expected_languages if not (resolved / f"{language}.traineddata").is_file()
    ]
    if missing_languages:
        return (
            display_label,
            False,
            f"{resolved} missing traineddata: {', '.join(missing_languages[:6])}",
        )
    return (display_label, True, str(resolved))


def find_vobsub_tesseract(
    workspace_root: Path,
    app_root: Path,
    ocr_tool_path: str,
    *,
    allow_system_tools: bool,
    expected_languages: Iterable[str],
    which: Callable[[str], str | None] = shutil.which,
) -> tuple[Path | None, Path | None, str]:
    candidate_paths: list[Path] = []
    resolved_tool = resolve_health_path(workspace_root, app_root, ocr_tool_path, path_type="file")
    if resolved_tool is not None:
        tool_dir = resolved_tool.parent
        for relative in ("tesseract.exe", "Tesseract550/tesseract.exe", "Tesseract-OCR/tesseract.exe", "Tesseract302/tesseract.exe", "Tesseract/tesseract.exe"):
            candidate_paths.append(tool_dir / relative)
    for relative in VOBSUB_TESSERACT_CANDIDATES:
        for root in health_path_roots(workspace_root, app_root):
            candidate_paths.append(root / relative)

    missing_data: tuple[Path, Path, list[str]] | None = None
    seen: set[str] = set()
    for candidate in candidate_paths:
        key = str(candidate).casefold()
        if key in seen:
            continue
        seen.add(key)
        try:
            if not candidate.is_file():
                continue
            tesseract = candidate.resolve()
        except OSError:
            continue
        tessdata = tesseract.parent / "tessdata"
        missing_languages = [
            language for language in expected_languages if not (tessdata / f"{language}.traineddata").is_file()
        ]
        if not missing_languages:
            return tesseract, tessdata.resolve(), "ok"
        if missing_data is None:
            missing_data = (tesseract, tessdata, missing_languages)

    if allow_system_tools:
        found = which("tesseract.exe") or which("tesseract")
        if found:
            tesseract = Path(found)
            tessdata = tesseract.parent / "tessdata"
            missing_languages = [
                language for language in expected_languages if not (tessdata / f"{language}.traineddata").is_file()
            ]
            if not missing_languages:
                return tesseract, tessdata, "ok"
            return tesseract, tessdata, f"missing traineddata: {', '.join(missing_languages[:6])}"

    if missing_data is not None:
        return missing_data[0], missing_data[1], f"missing traineddata: {', '.join(missing_data[2][:6])}"
    return None, None, "tesseract was not found in bundled VobSub OCR tool paths"


def vobsub_tesseract_health_row(
    workspace_root: Path,
    app_root: Path,
    config: object,
    *,
    required: bool,
    allow_system_tools: bool,
    which: Callable[[str], str | None] = shutil.which,
    run_capture_func: Callable[..., Any] | None = None,
    extra_popen_kwargs: dict[str, Any] | None = None,
) -> HealthRow:
    label = subtitle_health_label("Tesseract OCR (VobSub OCR)", required)
    ocr_tool_path = health_config_text(config, "VobSubOcrToolPath", VOBSUB_OCR_TOOL_DEFAULT)
    expected_languages = health_config_languages(config, "VobSubExtractLanguages")
    tesseract, tessdata, reason = find_vobsub_tesseract(
        workspace_root,
        app_root,
        ocr_tool_path,
        allow_system_tools=allow_system_tools,
        expected_languages=expected_languages,
        which=which,
    )
    if tesseract is not None and tessdata is not None and reason == "ok":
        if run_capture_func is not None:
            ok, detail = _probe_command(
                [str(tesseract), "--version"],
                run_capture_func=run_capture_func,
                timeout_seconds=10,
                extra_popen_kwargs=extra_popen_kwargs,
                label="Tesseract OCR health probe",
            )
            if not ok:
                return (label, False, _append_probe_detail(tesseract, ok, detail))
        return (label, True, f"{tesseract}; tessdata={tessdata}")
    if tesseract is not None and tessdata is not None:
        return (label, False, f"{tesseract}; {reason} in {tessdata}")
    return (label, False, reason)


def subtitle_tool_health_rows(
    workspace_root: Path,
    app_root: Path,
    config: object,
    *,
    which: Callable[[str], str | None] = shutil.which,
    run_capture_func: Callable[..., Any] | None = None,
    extra_popen_kwargs: dict[str, Any] | None = None,
) -> list[HealthRow]:
    allow_system_tools = health_config_bool(config, "AllowSystemTools", False)
    bdpgs_required = health_config_bool(config, "ConvertBdpgsToSrt", False)
    vobsub_required = health_config_bool(config, "ConvertVobSubToSrt", False)
    bdpgs_languages = health_config_languages(config, "BdpgsExtractLanguages")

    bdpgs_tool = health_config_text(config, "BdpgsOcrToolPath", BDPGS_OCR_TOOL_DEFAULT)
    bdpgs_tessdata = health_config_text(config, "BdpgsOcrTessdataPath", BDPGS_OCR_TESSDATA_DEFAULT)
    vobsub_tool = health_config_text(config, "VobSubOcrToolPath", VOBSUB_OCR_TOOL_DEFAULT)

    return [
        subtitle_config_file_health_row(
            workspace_root,
            app_root,
            "PgsToSrt (BDPGS OCR)",
            bdpgs_tool,
            required=bdpgs_required,
            allow_system_tools=allow_system_tools,
            which_names=("PgsToSrt.exe", "PgsToSrt"),
            which=which,
            missing_detail="BDPGS OCR tool not found.",
            run_capture_func=run_capture_func,
            extra_popen_kwargs=extra_popen_kwargs,
            probe_args=("--help",),
            accepted_probe_returncodes=(0, 1, 2),
        ),
        subtitle_config_directory_health_row(
            workspace_root,
            app_root,
            "PgsToSrt tessdata (BDPGS OCR)",
            bdpgs_tessdata,
            required=bdpgs_required and bool(bdpgs_tessdata),
            expected_languages=bdpgs_languages,
            blank_ok_detail="No BDPGS tessdata path is configured; OCR tool default search path will be used.",
            missing_detail="BDPGS OCR tessdata folder not found.",
        ),
        subtitle_config_file_health_row(
            workspace_root,
            app_root,
            "SubtitleEdit.exe (VobSub OCR)",
            vobsub_tool,
            required=vobsub_required,
            allow_system_tools=allow_system_tools,
            which_names=("SubtitleEdit.exe", "SubtitleEdit", "seconv.exe", "seconv"),
            which=which,
            unsupported_leaf_names=("seconv.exe", "seconv.dll"),
            missing_detail="VobSub OCR tool not found.",
            run_capture_func=run_capture_func,
            extra_popen_kwargs=extra_popen_kwargs,
            probe_args=("--help",),
            accepted_probe_returncodes=(0, 1, 2),
        ),
        vobsub_tesseract_health_row(
            workspace_root,
            app_root,
            config,
            required=vobsub_required,
            allow_system_tools=allow_system_tools,
            which=which,
            run_capture_func=run_capture_func,
            extra_popen_kwargs=extra_popen_kwargs,
        ),
    ]


def nvidia_smi_health_row(nvidia_smi: str | None) -> HealthRow:
    if nvidia_smi:
        return ("nvidia-smi (optional)", True, nvidia_smi)
    return ("nvidia-smi (optional)", False, "Not found - GPU encoder telemetry unavailable")


def config_schema_health_rows(resolved: Any) -> list[HealthRow]:
    config_path = getattr(resolved, "config_path", None)
    config = getattr(resolved, "config_data", None)
    if config_path is None:
        return [("Config schema", False, "Config path is not resolved.")]
    try:
        if not Path(config_path).is_file():
            return [("Config schema", False, f"Config file is missing: {config_path}")]
    except OSError as exc:
        return [("Config schema", False, f"Config file is not reachable: {exc}")]
    if not isinstance(config, Mapping):
        return [("Config schema", False, "Resolved config data is unavailable.")]
    try:
        Config.model_validate(dict(config))
    except Exception as exc:
        return [("Config schema", False, f"{config_path}; schema validation failed: {_output_snippet('', str(exc))}")]
    return [("Config schema", True, f"{config_path}; active config loaded and validated")]


def _configured_directory_candidate(workspace_root: Path, value: Any) -> Path | None:
    text = _text(value)
    if not text:
        return None
    raw = Path(text)
    if raw.is_absolute():
        return raw
    return workspace_root / raw


def _configured_directory_health_row(label: str, workspace_root: Path, value: Any, *, optional: bool = False) -> HealthRow:
    display_label = f"{label} (optional)" if optional else label
    candidate = _configured_directory_candidate(workspace_root, value)
    if candidate is None:
        return (display_label, False, "Path is not configured.")
    try:
        if candidate.is_dir():
            return (display_label, True, str(candidate.resolve()))
        if candidate.exists():
            return (display_label, False, f"{candidate} exists but is not a directory.")
    except OSError as exc:
        return (display_label, False, f"{candidate} is not reachable: {exc}")
    return (display_label, False, f"Directory not found: {candidate}")


def configured_root_health_rows(resolved: Any) -> list[HealthRow]:
    workspace_root = Path(getattr(resolved, "workspace_root", Path.cwd()))
    config = dict(getattr(resolved, "config_data", {}) or {})
    specs = (
        ("Configured root: SourceMovies", config.get(KEY_SOURCE_MOVIES) or getattr(resolved, "source_movies", None)),
        ("Configured root: SourceTV", config.get(KEY_SOURCE_TV) or getattr(resolved, "source_tv", None)),
        ("Configured root: Outsource", config.get(KEY_OUTSOURCE)),
        ("Configured root: LocalBase", config.get(KEY_LOCAL_BASE) or getattr(resolved, "local_base", None)),
    )
    return [_configured_directory_health_row(label, workspace_root, value) for label, value in specs]


def library_output_health_rows(resolved: Any) -> list[HealthRow]:
    workspace_root = Path(getattr(resolved, "workspace_root", Path.cwd()))
    config = dict(getattr(resolved, "config_data", {}) or {})
    rows: list[HealthRow] = []
    try:
        profiles = effective_library_profiles_from_config(config)
    except Exception as exc:
        return [("Library output roots", False, f"LibraryProfiles could not be normalized: {exc}")]

    enabled_profiles = [profile for profile in profiles if _bool_value(profile.get("enabled", True), True)]
    for profile in enabled_profiles:
        label = _text(profile.get("name") or profile.get("id") or "Library")
        output_path = profile.get("effective_output_root") or profile.get("output_path")
        rows.append(_configured_directory_health_row(f"Library output root: {label}", workspace_root, output_path))
        if _bool_value(profile.get("promotion_enabled", False), False):
            rows.append(
                _configured_directory_health_row(
                    f"Library promotion destination: {label}",
                    workspace_root,
                    profile.get("promotion_destination"),
                )
            )

    promotion_enabled = _bool_value(config.get(KEY_FINAL_LIBRARY_PROMOTION_ENABLED), False)
    for rule in _coerce_final_library_rules(config.get(KEY_FINAL_LIBRARY_PROMOTION_RULES)):
        if not promotion_enabled or not _bool_value(rule.get("enabled", True), True):
            continue
        label = _text(rule.get("label") or rule.get("id") or "Rule")
        destination = _first_text(rule, "destination_root", "destinationRoot", "destination")
        rows.append(_configured_directory_health_row(f"Final library destination: {label}", workspace_root, destination))

    if rows:
        return rows
    return [("Library output roots (optional)", True, "No enabled Library Profiles or Final Library destination roots are configured.")]


def _first_text(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        text = _text(mapping.get(key))
        if text:
            return text
    return ""


def _coerce_final_library_rules(raw: Any) -> list[dict[str, Any]]:
    if raw in (None, "", False):
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            return []
    if isinstance(raw, Mapping):
        raw = [raw]
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def runtime_state_health_rows(resolved: Any) -> list[HealthRow]:
    state_root = getattr(resolved, "state_root", None) or (
        Path(getattr(resolved, "local_base")) / "State" if getattr(resolved, "local_base", None) else None
    )
    if state_root is None:
        return [("Runtime state files", False, "State root is not resolved.")]
    state_root = Path(state_root)
    try:
        if not state_root.is_dir():
            return [("Runtime state files", False, f"State root is missing or not a directory: {state_root}")]
        list(state_root.iterdir())
    except OSError as exc:
        return [("Runtime state files", False, f"State root is not readable: {exc}")]

    checked: list[str] = []
    errors: list[str] = []
    for attr in RUNTIME_STATE_FILE_ATTRS:
        path = getattr(resolved, attr, None)
        if path is not None:
            _check_state_file(Path(path), checked, errors)
    active_jobs_path = getattr(resolved, "active_jobs_path", None) or (state_root / "ActiveJobs")
    _check_state_directory_json_files(Path(active_jobs_path), checked, errors)
    sqlite_ok, sqlite_detail = _sqlite_state_check(state_root)

    if errors:
        return [("Runtime state files", False, "; ".join(errors[:6])), ("SQLite mirror (optional)", sqlite_ok, sqlite_detail)]
    detail = f"State root readable; parsed {len(checked)} existing state artifact(s)."
    if checked:
        detail += " Checked: " + ", ".join(checked[:8])
    return [("Runtime state files", True, detail), ("SQLite mirror (optional)", sqlite_ok, sqlite_detail)]


def _check_state_file(path: Path, checked: list[str], errors: list[str]) -> None:
    try:
        if not path.is_file():
            return
    except OSError as exc:
        errors.append(f"{path.name} is not reachable: {exc}")
        return
    try:
        if path.suffix.casefold() == ".jsonl":
            _read_jsonl(path)
        elif path.suffix.casefold() == ".json":
            json.loads(path.read_text(encoding="utf-8-sig"))
        else:
            return
        checked.append(path.name)
    except Exception as exc:
        errors.append(f"{path.name} parse failed: {exc}")


def _check_state_directory_json_files(path: Path, checked: list[str], errors: list[str], *, max_items: int = 24) -> None:
    try:
        if not path.is_dir():
            return
        candidates = sorted(path.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError as exc:
        errors.append(f"{path.name} directory is not readable: {exc}")
        return
    for candidate in candidates[:max_items]:
        _check_state_file(candidate, checked, errors)


def _read_jsonl(path: Path, *, max_lines: int = 5000) -> None:
    with path.open("r", encoding="utf-8-sig") as handle:
        for index, line in enumerate(handle, start=1):
            if index > max_lines:
                break
            text = line.strip()
            if text:
                json.loads(text)


def _sqlite_state_check(state_root: Path) -> tuple[bool, str]:
    db_path = state_root / STATE_DB_FILENAME
    if not db_path.is_file():
        return True, f"{db_path} not present; JSON state remains authoritative."
    conn: sqlite3.Connection | None = None
    try:
        uri = db_path.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=2.0)
        conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
    except Exception as exc:
        return False, f"{db_path}; read-only open failed: {exc}"
    finally:
        if conn is not None:
            conn.close()
    return True, f"{db_path}; read-only open ok"


def api_contract_health_rows() -> list[HealthRow]:
    try:
        from mediapipeline.desktop.api.contract import LOCAL_API_ROUTE_CONTRACT
    except Exception as exc:
        return [("API contract", False, f"Local API route contract could not be imported: {exc}")]
    routes = {str(route.get("path") or "") for route in LOCAL_API_ROUTE_CONTRACT if isinstance(route, Mapping)}
    missing = [route for route in REQUIRED_API_CONTRACT_ROUTES if route not in routes]
    if missing:
        return [("API contract", False, "Missing read route contract(s): " + ", ".join(missing))]
    status_note = "/api/status is not an active route; /api/health and /api/snapshot are the current status surfaces."
    return [("API contract", True, f"{len(routes)} route contract(s) available. {status_note}")]


def process_guard_health_rows(resolved: Any, service: Any | None = None) -> list[HealthRow]:
    messages: list[str] = []
    informational: list[str] = []
    if service is not None:
        active_blocks = getattr(service, "active_job_close_block_messages", None)
        if callable(active_blocks):
            try:
                messages.extend(str(item) for item in active_blocks(resolved) if _text(item))
            except Exception as exc:
                messages.append(f"ActiveJobs could not be verified: {exc}")
        related = getattr(service, "find_related_pipeline_processes", None)
        if callable(related):
            try:
                processes = related(resolved)
                if processes:
                    pids = ", ".join(str(getattr(proc, "pid", "?")) for proc in processes[:8])
                    messages.append(f"Related MediaPipeline process PID(s) still running: {pids}")
            except Exception as exc:
                text = str(exc)
                if "psutil unavailable" in text.casefold():
                    informational.append(f"Related process inspection unavailable: {exc}")
                else:
                    messages.append(f"Related process inspection failed: {exc}")
    if messages:
        return [("Process guard", False, "; ".join(messages[:6]))]
    if informational:
        return [("Process guard", True, "No active ActiveJobs blockers were detected. " + "; ".join(informational[:3]))]
    return [("Process guard", True, "No active ActiveJobs blockers or related MediaPipeline processes were detected.")]


def bundle_layout_health_rows(workspace_root: Path, app_root: Path) -> list[HealthRow]:
    missing: list[str] = []
    for rel_path, label in CANONICAL_LAYOUT_PATHS:
        path = workspace_root / rel_path
        if not path.exists():
            missing.append(f"{label}: {path}")
    reintroduced = [name for name in REMOVED_ROOT_LAUNCHERS if (workspace_root / name).exists()]
    pipeline_modules = workspace_root / "ops" / "pipeline" / "engine"
    try:
        dotted_modules = list(pipeline_modules.glob("*.*.ps1")) if pipeline_modules.is_dir() else []
    except OSError:
        dotted_modules = []
    if missing:
        return [("Bundle layout", False, "Missing expected current layout path(s): " + "; ".join(missing[:6]))]
    if reintroduced:
        return [("Bundle layout", False, "Removed root launcher shim(s) reintroduced: " + ", ".join(reintroduced))]
    if dotted_modules:
        return [("Bundle layout", False, "Dotted ops/pipeline/engine PowerShell file(s) present: " + ", ".join(path.name for path in dotted_modules[:6]))]
    return [("Bundle layout", True, f"Canonical scripts, bundled runtimes, and WebView assets present under {app_root}; removed root launchers absent.")]


def find_ass_to_srt_script(workspace_root: Path, app_root: Path) -> Path | None:
    for candidate in (
        workspace_root / "src" / "mediapipeline" / "pipeline" / "ass_to_srt_cli.py",
        app_root / "pipeline" / "ass_to_srt_cli.py",
    ):
        if candidate.exists():
            return candidate
    return None


def ass_to_srt_missing_row() -> HealthRow:
    return ("ass_to_srt (subtitle converter)", False, "Script not found under src/mediapipeline/pipeline/")


def ass_to_srt_result_row(script_path: Path, returncode: int, stderr: str) -> HealthRow:
    # Exit 2 = script loaded OK (arg-count guard), anything else = broken imports.
    if int(returncode) == 2:
        return ("ass_to_srt (subtitle converter)", True, str(script_path))
    text = str(stderr or "").strip()
    snippet = text.split("\n")[0][:120] if text else f"exit {returncode}"
    return ("ass_to_srt (subtitle converter)", False, snippet)


def ass_to_srt_exception_row(exc: Exception) -> HealthRow:
    return ("ass_to_srt (subtitle converter)", False, str(exc))
