# Global Generated Final Independent Review

Reviewer: `/root/active_docs_independent`.

Fresh external-output baseline: 6,499 tracked paths. After excluding audit paths and every current path returned by `load_second_review_attestations`, the exact high-risk generated scope was 1,796 paths.

The set contains 1,792 per-source summaries and four aggregate maps: `DEPENDENCY_GRAPH.md`, `FEATURE_FILE_MAP.md`, `PIPELINE_MAP.md`, and `PROJECT_INDEX.md`.

All 1,792 summaries were independently checked from current bytes. Every mapped source exists; normalized source SHA-256, schema 2, generator fingerprint, frontmatter, authority footer, references, and exact `refresh_summaries.render_summary` output match. Eleven rows retain the first-pass `AUDIT-FIND-W12-010` disposition `resolved-in-audit`, accurately describing an earlier non-atomic snapshot rather than a current render defect.

`PIPELINE_MAP.md` passes its dedicated canonical check. `PROJECT_INDEX.md` and `DEPENDENCY_GRAPH.md` fail the project-index check and remain finding-backed by confirmed `AUDIT-FIND-COV-001`. `FEATURE_FILE_MAP.md` fails its dedicated check and remains finding-backed by confirmed `AUDIT-FIND-W12-003`. No unsupported-provenance artifact was falsely attested and no new finding was required.

Published status: exactly 1,796 unique `generated_verified` attestations, each bound to the fresh current artifact hash, current first reviewer, exact first-pass finding set, current disposition, and applicable error record.

Validation: exact candidate-set equality, 1,796 unique paths, zero artifact-hash mismatches, zero missing first reviews, exact first-review finding/status joins, finding/error schema joins, and independent reviewer separation. Representative real-media validation is not required.
