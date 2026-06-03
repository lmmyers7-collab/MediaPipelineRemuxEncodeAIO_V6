from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Iterable

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
            "Pipeline/Tools/ffmpeg/bin/ffmpeg.exe",
            "Pipeline/Tools/ffmpeg/bin/ffmpeg",
        ),
    ),
    (
        "ffprobe",
        "ffprobe.exe",
        "ffprobe",
        (
            "Pipeline/Tools/ffmpeg/bin/ffprobe.exe",
            "Pipeline/Tools/ffmpeg/bin/ffprobe",
        ),
    ),
    (
        "mkvmerge",
        "mkvmerge.exe",
        "mkvmerge",
        (
            "Pipeline/Tools/MKVToolNix/mkvmerge.exe",
            "Pipeline/Tools/MKVToolNix/mkvmerge",
        ),
    ),
    (
        "mkvextract",
        "mkvextract.exe",
        "mkvextract",
        (
            "Pipeline/Tools/MKVToolNix/mkvextract.exe",
            "Pipeline/Tools/MKVToolNix/mkvextract",
        ),
    ),
)


def powershell_health_row(pwsh: str | None) -> HealthRow:
    if pwsh:
        return ("PowerShell (pwsh)", True, pwsh)
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
            results.append((tool_name, True, found))
        else:
            results.append((tool_name, False, "Not found in bundled Tools or system PATH"))
    return results


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
        workspace_root / "Pipeline",
        app_root / "Pipeline",
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
        ),
        vobsub_tesseract_health_row(
            workspace_root,
            app_root,
            config,
            required=vobsub_required,
            allow_system_tools=allow_system_tools,
            which=which,
        ),
    ]


def nvidia_smi_health_row(nvidia_smi: str | None) -> HealthRow:
    if nvidia_smi:
        return ("nvidia-smi (optional)", True, nvidia_smi)
    return ("nvidia-smi (optional)", False, "Not found - GPU encoder telemetry unavailable")


def find_ass_to_srt_script(workspace_root: Path, app_root: Path) -> Path | None:
    for name in ("ass_to_srt.py", "ass_to_srt.py"):
        for base in (workspace_root, app_root):
            candidate = base / "Pipeline" / name
            if candidate.exists():
                return candidate
    return None


def ass_to_srt_missing_row() -> HealthRow:
    return ("ass_to_srt (subtitle converter)", False, "Script not found in Pipeline/")


def ass_to_srt_result_row(script_path: Path, returncode: int, stderr: str) -> HealthRow:
    # Exit 2 = script loaded OK (arg-count guard), anything else = broken imports.
    if int(returncode) == 2:
        return ("ass_to_srt (subtitle converter)", True, str(script_path))
    text = str(stderr or "").strip()
    snippet = text.split("\n")[0][:120] if text else f"exit {returncode}"
    return ("ass_to_srt (subtitle converter)", False, snippet)


def ass_to_srt_exception_row(exc: Exception) -> HealthRow:
    return ("ass_to_srt (subtitle converter)", False, str(exc))
