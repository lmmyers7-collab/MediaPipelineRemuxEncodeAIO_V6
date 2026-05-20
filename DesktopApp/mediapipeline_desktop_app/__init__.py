from __future__ import annotations

import re
from pathlib import Path


APP_NAME = "MediaPipelineRemuxEncodeAIO"
_APP_VERSION_FALLBACK = "v6.000"
_PRODUCT_VERSION_PATTERN = re.compile(
    r"function\s+Get-MediaPipelineProductVersion\s*\{[^{}]*return\s+['\"](?P<version>v\d+\.\d{3})['\"]",
    re.IGNORECASE | re.DOTALL,
)


def _read_pipeline_product_version() -> str:
    for root in Path(__file__).resolve().parents:
        versioning = root / "Pipeline" / "Modules" / "Versioning.ps1"
        if not versioning.is_file():
            continue
        try:
            match = _PRODUCT_VERSION_PATTERN.search(versioning.read_text(encoding="utf-8"))
        except OSError:
            return _APP_VERSION_FALLBACK
        if match:
            return match.group("version")
    return _APP_VERSION_FALLBACK


APP_VERSION = _read_pipeline_product_version()
PIPELINE_SIDECAR_VERSION = "1.0"
APP_CHUNK = ""
