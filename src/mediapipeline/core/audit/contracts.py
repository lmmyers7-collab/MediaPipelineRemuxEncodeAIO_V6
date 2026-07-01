from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from mediapipeline.core.paths.media_paths import (
    derive_tv_lookup_title,
    is_season_only_lookup,
)


@dataclass
class AuditRecord:
    source_csv: Path
    row: dict[str, str]

    @property
    def path(self) -> Path | None:
        raw = self.row.get("Path", "").strip()
        return Path(raw) if raw else None

    @property
    def relative_path(self) -> str:
        return self.row.get("RelativePath", "").strip()

    @property
    def source_root(self) -> str:
        return self.row.get("SourceRoot", "").strip()

    @property
    def lookup_title(self) -> str:
        raw = self.row.get("LookupTitle", "").strip()
        if self.media_type == "TV" and (is_season_only_lookup(raw) or not raw):
            derived = derive_tv_lookup_title(str(self.path or self.relative_path))
            if derived:
                return derived
        return raw

    @property
    def media_type(self) -> str:
        return self.row.get("MediaType", "").strip()

    @property
    def effective_bucket(self) -> str:
        return self.row.get("EffectiveBucket", "").strip() or self.row.get("Bucket", "").strip()

    @property
    def priority_fix_level(self) -> str:
        return self.row.get("PriorityFixLevel", "").strip()

    @property
    def priority_score(self) -> int:
        raw = self.row.get("PriorityScore", "").strip()
        try:
            return int(float(raw))
        except ValueError:
            return 0

    @property
    def primary_issue_code(self) -> str:
        return self.row.get("PrimaryIssueCode", "").strip()

    @property
    def primary_suggested_action(self) -> str:
        return self.row.get("PrimarySuggestedAction", "").strip()

    @property
    def issue_messages(self) -> str:
        return self.row.get("IssueMessages", "").strip()

    @property
    def normalized_lookup_title(self) -> str:
        base = self.lookup_title.strip()
        if not base and self.path:
            base = self.path.stem
        if not base:
            base = self.relative_path
        normalized = base.casefold()
        normalized = re.sub(r"\((?:19|20)\d{2}\)", " ", normalized)
        normalized = re.sub(r"\bseason\s*\d{1,2}\b", " ", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bs\d{1,2}\b", " ", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized
