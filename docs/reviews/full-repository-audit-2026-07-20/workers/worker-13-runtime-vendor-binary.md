# Worker 13 — Runtime, Vendor, and Binary

## Outcome

The live ledger assigns **15**, not 16, paths to `worker-13-runtime-vendor-binary`. All 15 are terminal at their current SHA-256 with `binary_inventoried` and verified obligation `binary_metadata_and_packaging`.

Canonical evidence:

- `worker-13-runtime-vendor-binary-review.jsonl`: 15 exact-path rows
- `worker-13-runtime-vendor-binary-findings.jsonl`: 3 confirmed findings
- `worker-13-runtime-vendor-binary-errors.jsonl`: 12 non-blocking command/tool errors with retries

Every path is a tracked ordinary Git blob with mode `100644`; none uses Git LFS. The assigned payload is 3,350,520 bytes.

## Inventory reconciliation

| Group | Paths | Bytes | Type and purpose | Default portable package | Result |
|---|---:|---:|---|---|---|
| `.codex-remote-attachments` | 9 | 1,488,782 | JPEG 597x1280 RGB mobile-game screenshots; transient assistant/user inputs with no active consumer | Included; binary content scan skipped | `AUDIT-FIND-W13-002` |
| Tauri branding | 4 | 1,600,190 | One 1254px PNG, one 256px PNG, and two 256px ICO names | Included; manifest SHA-256 applies | Reconciled, no finding |
| `docs/ui/Refactoring_UI_text_only.docx` | 1 | 71,272 | OOXML text-only UI reference document | Excluded as local Office working document; still Git-distributed | `AUDIT-FIND-W13-003` |
| CSV rerun evidence | 1 | 190,276 | PNG 1294x1399 operational proof | Included; binary content scan skipped | `AUDIT-FIND-W13-001` |

Exact sizes, SHA-256 values, Git blob IDs, type/mode, provenance commits, purpose/owner assessment, package decision, integrity coverage, license/security relevance, and duplicate disposition are recorded per path in the review JSONL.

## Findings

- **AUDIT-FIND-W13-001 (P1, high):** the portable-package-included CSV rerun screenshot exposes `lmmye`, `\\LAYNE-SERVER\Users\Layne\Videos\outsource\Movies`, a local AppData path, process/run IDs, and timestamps. Release manifest hashing preserves integrity but does not prevent disclosure.
- **AUDIT-FIND-W13-002 (P2, high):** nine unrelated Uma Musume screenshots are tracked and package-included. They have no active product/documentation consumer; code-context tooling already excludes the attachment namespace, while ignore/release policy does not.
- **AUDIT-FIND-W13-003 (P1, high):** the tracked DOCX is a substantial text-only conversion of the paid *Refactoring UI* work without a repository permission/provenance record. This is an unresolved redistribution-entitlement issue, not a legal conclusion. The file is excluded from portable release but remains distributed by Git.

## Visual, structural, duplication, and provenance evidence

All 14 images were individually viewed. The nine attachment JPEGs contain mobile-game roster/card/selection screens and no EXIF or visible personal identity. The release-evidence PNG visibly contains the identifiers cited above.

The DOCX was opened read-only in Word 16, exported to PDF, rendered through bundled Poppler, and inspected across all 41 pages. It contains 886 paragraphs, 15,723 words, eight main Heading 1 sections, no tables or images, and no external relationships, macros, comments, tracked revisions, or embeddings. Core properties identify Layne Myers and describe a conversion from a user-provided PDF. The official [Refactoring UI site](https://refactoringui.com/) identifies Adam Wathan and Steve Schoger's work as a paid Tailwind Labs book. Bounded searches found no active inbound consumer.

`icon.ico` and `launcher-logo.ico` are exact byte/Git-blob duplicates. This is intentional compatibility: the configured Tauri icon uses `launcher-logo.ico`, while prerequisite/release checks require `icon.ico`. Both PNG renditions are visually the same branding family; the 1254px and 256px PNG filenames have no direct active consumer, but their containing trees are packaged. No additional finding was raised for the small, first-party branding redundancy.

Attachment provenance is commit `039658158d8439a868eff3c8c37e314845e9e22a`; branding provenance is baseline commit `da13cd22f194f7fa47b8c4eb28be16a70d9a09df` or commit `4834159705080f010ee34a5c7fa7c42debc74d0b`; the evidence PNG was added by `579375fbf636ef7cbbabfedb87fac569c30633fd`.

## Error and validation closure

Twelve failed, warning-producing, truncated, unavailable-format, or incorrect-aggregation attempts are preserved in the error fragment. Each has a successful bounded retry or alternate path; none blocks coverage.

Validation results:

- JSONL parse/count: 15 review rows, 3 findings, 12 errors.
- `prepare_finding_records`: 72 global findings, 0 fragment issues.
- `prepare_error_records`: 339 global errors, 0 fragment issues.
- `prepare_review_rows`: 6,064 live rows, 0 issues; W13 = 15 unique terminal `binary_inventoried` paths.
- Independent rehash/join check: all 15 current SHA-256 values match and every review row exactly matches its current path-local finding set.
- Source bytes were not modified. No central audit, product, operator, generated, or release-policy file was edited.

## Independent P1 disposition

Distinct reviewer `/root/coordinator_w13` rehashed and independently inspected the exact PNG and DOCX bytes, reran their current release-policy predicates, checked Git/provenance evidence, parsed the DOCX structure/core properties with the bundled document runtime, and compared its identity/headings with the official publisher page. `AUDIT-FIND-W13-001` and `AUDIT-FIND-W13-003` remain confirmed. The two-row `worker-13-runtime-vendor-binary-independent-attestation.jsonl` passes the global schema/hash/finding-set join with zero issues; the companion Markdown report records the bounded proof. W13-002 is P2 and the assigned files are not classified high risk, so no additional W13 second-review row is required by gate 10 at current hashes.
