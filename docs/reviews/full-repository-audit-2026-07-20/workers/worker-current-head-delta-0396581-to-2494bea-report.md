# Current-HEAD audit delta reconciliation

Snapshot: `2026-07-21T10:12:56.6106485-04:00`  
Old audit baseline: `039658158d8439a868eff3c8c37e314845e9e22a`  
Current audited HEAD: `2494bea1fd6280f41bec3f56e21b8bd98dd20829`  
Change packet: `MP-CHANGE-2026-0720-011` (identified but not edited by this audit-only worker).

This report reconciles file identity and coverage only. It makes no product, generated-canonical, central-ledger, finding-ledger, error-ledger, or change-packet edits. Representative real-media validation is not required because no runtime behavior or media-processing path was executed or changed.

## Universe reconciliation

The old commit contains 6,061 tracked paths and the current commit contains 6,499. The 873 name-status entries affect 851 current paths and 421 old paths; 5,648 current paths retain their old path and Git blob identity.

| Raw Git status | Entries |
| --- | ---: |
| A | 452 |
| C050 | 1 |
| C052 | 1 |
| C054 | 1 |
| C059 | 1 |
| C063 | 2 |
| C064 | 1 |
| C065 | 1 |
| D | 22 |
| M | 337 |
| R052 | 4 |
| R100 | 50 |

| Normalized change class | Entries |
| --- | ---: |
| addition | 452 |
| copy_derived_addition | 8 |
| deletion | 22 |
| modification | 337 |
| rename | 54 |

Copy statuses are additions with source provenance: 452 paths are pure additions and 8 are copy-derived additions, for 460 added current paths. Renames comprise 50 `R100` byte-identical moves and 4 `R052` moves with changed content.

## Exact baseline actions

| Action | Paths |
| --- | ---: |
| Add current baseline rows | 511 |
| Refresh existing Git blob identities | 340 |
| Remove stale old-path rows | 76 |
| Unchanged current path/blob identities | 5648 |

The 511 adds plus 340 refreshes cover all 851 affected current paths. The 76 removals are the 54 rename source paths plus 22 deleted paths.

## Review-evidence disposition

| Disposition | Current paths |
| --- | ---: |
| Exact-current-hash achieved evidence already present | 138 |
| R100 evidence reusable after path/authority rebinding | 50 |
| Current-hash review still required | 663 |
| Total affected current paths | 851 |

No `R100` rename lacks old-path exact-hash evidence. Similarity-only renames/copies do not reuse semantic evidence. A commit status alone never counts as review evidence.

| Current file category | Affected paths |
| --- | ---: |
| active documentation | 78 |
| behavior-defining configuration/schema/workflow | 272 |
| first-party executable source | 111 |
| first-party test or fixture | 52 |
| generated artifact | 260 |
| historical archived evidence | 6 |
| metadata/packaging | 72 |

| Likely current audit worker | Affected paths |
| --- | ---: |
| worker-01-backend-api-application | 7 |
| worker-02-config-settings-library | 3 |
| worker-03-queue-process-status | 49 |
| worker-05-media-policy | 1 |
| worker-06-contracts-storage-observability | 14 |
| worker-07-webview-common | 31 |
| worker-08-webview-pages | 17 |
| worker-10-ops-workflows | 75 |
| worker-11-tests-tooling | 76 |
| worker-12-docs-generated-other | 578 |

| Likely worker | Current-hash reviews required |
| --- | ---: |
| worker-01-backend-api-application | 1 |
| worker-02-config-settings-library | 2 |
| worker-03-queue-process-status | 9 |
| worker-06-contracts-storage-observability | 2 |
| worker-07-webview-common | 20 |
| worker-08-webview-pages | 6 |
| worker-10-ops-workflows | 24 |
| worker-11-tests-tooling | 21 |
| worker-12-docs-generated-other | 578 |

## Current finding linkage

`AUDIT-FIND-W10-020` is linked, without duplication, to 3 delta paths:

- `docs/inventories/TEST_SUITE_SUBSYSTEM_INVENTORY.v1.json` (`A`)
- `ops/pipeline/tests/Unit/Invoke-ReleasePackagePolicyChecks.ps1` (`M`)
- `ops/scripts/release/release_policy.ps1` (`M`)

Its fourth location, `ops/scripts/release/build.ps1`, is unchanged between these commits and therefore is outside this delta manifest.

## Worktree binding

The canonical tracked hash in the manifest is the blob at current HEAD. 32 affected tracked paths differed from those bytes at the snapshot:

- `docs/change_control/CHANGELOG.md`: worktree SHA-256 `bd8c0f3ee1551e45117b386e5bc553aa55c1ca65553837d037dc81bf97eb9b7e`; HEAD SHA-256 `6a6923c01e989651b34f6bacdfda1d2477792716afd3e0dce39cd29f2a7c48df`
- `docs/change_control/CHANGE_INDEX.md`: worktree SHA-256 `ed4774e606bf6835d29ca04b03f6e6f11b38fb652004284b5470c709efd4e76c`; HEAD SHA-256 `69edb2e8b905ed4a3ad1039feea170cb524263689037f52e4f452b3acc6f3d45`
- `docs/generated/DOC_ARCHIVE_CANDIDATE_SCAN.md`: worktree SHA-256 `39b59683edaa65c50b3a81046135543c258f73459d6e0156c5b58c39f7b616d3`; HEAD SHA-256 `60711f349f908019a14ab5fce873920bd1c057cc839e5df4366b6e6b901c2227`
- `docs/inventories/API_ROUTE_INVENTORY.md`: worktree SHA-256 `9d8b056b3371e3729e71e680823ed312f672d6676cf9fd5d5e333507c9691b5a`; HEAD SHA-256 `cdd80f4452b0d232266f89bfc7bce9f4f7e0a05cb08ff0edd7990e9a695b7cf8`
- `docs/inventories/STATE_FILE_SCHEMA_REFERENCE.md`: worktree SHA-256 `e820ca73993799a23c38e05eb16b617fa085f5f9fe77eb776bb44009698557fe`; HEAD SHA-256 `cca38e6bd3e63b7258452046fda960ce9680c4e708c8fac6dda755cecd449fba`
- `docs/reviews/full-repository-audit-2026-07-20/workers/coordinator-errors.jsonl`: worktree SHA-256 `53a00bef1833fb3d59c0131934c73f0469d510acf4067402adfd0592808ba146`; HEAD SHA-256 `5b6ea78d0e6b53666c3833b60d37b64fd108a506cbb395d9277e7e022776ff46`
- `docs/reviews/full-repository-audit-2026-07-20/workers/worker-04-publish-completed-rename-review.jsonl`: worktree SHA-256 `2eb4f630cce6ace80a74a80a55ffd451efcf3bb95458569362137e73a7c00551`; HEAD SHA-256 `520fe41a257e6615a52841277805ce2eb86680aa28483244c237493adb2abbab`
- `docs/reviews/full-repository-audit-2026-07-20/workers/worker-10-ops-workflows-findings.jsonl`: worktree SHA-256 `275c565314ee744567480acadb9d462cca0b3863bafa7ab2a0f486ae47422c4d`; HEAD SHA-256 `dc0818faa0b0ac1c8337948e38dc873ce553b159407a19e2b8661447859d44cb`
- `docs/testing/TEST_COVERAGE_MATRIX.md`: worktree SHA-256 `caa4509ae01562c467515cbd315b628166124703f02f3f0851ea877aec151da8`; HEAD SHA-256 `4fe8052b246ff1b49c7bc7feb0e1e8501a4813e482e15e15a8117713a798c67a`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-011.json`: worktree SHA-256 `47ee547ad13d68d52c5f28b7d1197af14998bbdb00deffe9e4076afb39d3218f`; HEAD SHA-256 `91e3aacbc457b833b4c127bdd82a37cbd130c9340cb0c1b973ed8dafbed06c9d`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-012.json`: worktree SHA-256 `74133bad7d3eebe14b20e64eadda01ea551dd7c00f6336fac9e4c6998062279e`; HEAD SHA-256 `bfa15f6ff035907a12a9eb65da27dc5b65beb9ea1e8af7d85b8986a2eb1f09ff`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-013.json`: worktree SHA-256 `2fe0d824b8acd14ecb7b83b70b09c6e72388608e0733e31478aa46f41e980ad7`; HEAD SHA-256 `931f340743a03348bd2afbfce77ce353b35ed994d481cea4a46a65ee2ec85b8c`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-014.json`: worktree SHA-256 `80efa26fd615847f8f8692e5f6a714b82fd1ed4e5275a26948975c58730cd9e1`; HEAD SHA-256 `06365a21c5f79a3d1475cca413decd27357df938dfffb2054e059c911b051932`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-015.json`: worktree SHA-256 `1b9a415586cd587592ca27c310a2616f01b533221e8457a6686fc8c8bd934441`; HEAD SHA-256 `26daf209bd568aa7b1cd5c57533a5cef12284146b57cba3e72325df481b233bc`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-016.json`: worktree SHA-256 `53c594f8e24e64dc4b7d987eed3ff2127bec2de391d2781af52420feb4dc1120`; HEAD SHA-256 `593cad409209e1e2433868271b1f03dce0b0a973c123ec11d586a2c5db6ea8a0`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-017.json`: worktree SHA-256 `228e7b2982d32cad67f27b4015eac9c2e0b1f2045f8fab54e30214c99e90514c`; HEAD SHA-256 `ae481128715058059e807298b9c184966ff03ba7924e4057cec511a7856b2e19`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-018.json`: worktree SHA-256 `c669bb10730003c92446648cebceca7432d0fe7047516cce54fe33f00490b60b`; HEAD SHA-256 `21994f338c0019924d4a762fbb39632800310826d0244a18bdc8b233a9d57b5e`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-020.json`: worktree SHA-256 `b2b0990e642871799acadc023a78e01e9e56dcd3daaf1594f25c0b6d0f669f1a`; HEAD SHA-256 `abafe182273b4400aa20a5069d1c0cf922ca5d5df4b2e79cc5e0ced77e60560b`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-021.json`: worktree SHA-256 `726a2496eec102d6830435e63e10156276149357df9ce1b4c1e6ed98ed4bba49`; HEAD SHA-256 `f4466b81bd6a6bc8671b377b53b5a4c3aea244992e62df4c9020d4253e6c2189`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-022.json`: worktree SHA-256 `6c5aa5299147b4a3745abf225a350d73343900be89a60cebc415fe3eed715199`; HEAD SHA-256 `0502f556208e16f40f18a566ae5093de513ec1cd414acc7b42ad3d3f3abc9c17`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-023.json`: worktree SHA-256 `6b7d7899d6bdbad7c44ccb5f6eecf25aaac5a7d65facd9add70c3879daaa7ada`; HEAD SHA-256 `a61b906aabdfb9225a9937b22a7c02fcf1cde47db8329270874c073a7a8dd4b6`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-024.json`: worktree SHA-256 `a9e01630c33c1c2e92e6969cf4273767c1669a5a94dc0221cc0af068cc3f464c`; HEAD SHA-256 `4bb7f43f9c064445379885a301c7aa863c1be4d9d29011e95daf42734eb23729`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-025.json`: worktree SHA-256 `05dd85834543408f10cbec822a4a28e96a12dc58810ddd04fc4777236bd3b81f`; HEAD SHA-256 `962f1f51301b0982ae10a969d0c2c20e8497626f21737ec1b224b073bcd00055`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-026.json`: worktree SHA-256 `67bcdea5779238f5f1405950b95c30b3591baaf05e17bec7b993beceb47d9d6c`; HEAD SHA-256 `c6431047fba689f0e4992b78e84bf78a6f903b47220a03f95eb4d11109aa9fd8`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-027.json`: worktree SHA-256 `23f284ff17864199ac99bd99e6ad04ab84a1dc1fde36edcb2dd9842594278929`; HEAD SHA-256 `b91f0494347649f948d72c4d8588d1deb0887c67dbc299fb148c3fbf8307cf9d`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-028.json`: worktree SHA-256 `89b9055098bbc20a223067dbb63a4d28b119fb85abdecb44ef3c21beaa7bee29`; HEAD SHA-256 `d1e258607d60353cb014efde9aace06c43f7e6e19ff0c2a61e22e59680148c79`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-029.json`: worktree SHA-256 `0713db22c544b256ad8d02c289e252bb7d48bdbda74785f57df873b797a92d22`; HEAD SHA-256 `d3f7b32e5c48a0abee40372dd46be36b2ef8c63e44ed0bb5232b308e95d44a4f`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-030.json`: worktree SHA-256 `f3626ff13e6e4d41c8acf6facbe2eabc274d3b430136c8a48676b37c85a8ec69`; HEAD SHA-256 `a75cfeaef4b9fa03ef86cec0077d1c09479acbd6b550846d209aefde95bad8bc`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0720-031.json`: worktree SHA-256 `109592892d15cdd0538ca4cd90657415c998f87b466b69d990da2d79f74ea758`; HEAD SHA-256 `f68922333d43a341f3a7e9b1d54582563722db9aca2ea83f1e6cd292378c5594`
- `ops/release/changes/unreleased/MP-CHANGE-2026-0721-001.json`: worktree SHA-256 `be0a631d5ca6feb42f08f0934ebcda555a05291527b015deb3d87c2a986cb2b1`; HEAD SHA-256 `0d92830cc90284e4fb43e711efdff5c3109ab401041c705a8b6c322d092760b3`
- `tests/python/desktop/test_application_facade_process_launch.py`: worktree SHA-256 `1055ee264f6d85ac92d50154199a6b4e233c5e8907b451132c5783610190d432`; HEAD SHA-256 `455a4bd6d2ea2add138a3442a683abf37638de1a8d89f079c90ef452ec742aa1`
- `tests/webview/test_webview_browser_run_monitor_smoke.py`: worktree SHA-256 `5e15e89ff7f80fd17aac8c653a921c1fad0691405ae90490be774c355db07787`; HEAD SHA-256 `7d37b183bbad7922fbbfc605638c8247d5275ef0141fb0986db20dced98b9e7d`

These are raw worktree-byte versus Git-blob differences, not 32 Git-dirty paths. Git's checkout normalization can produce a different SHA-256 while `git diff` remains clean; for example, `docs/change_control/CHANGELOG.md` is `i/lf w/crlf` and has no status/diff entry. Only paths reported by the captured Git status are concurrent edits. The manifest preserves both byte identities and does not silently substitute either one for current-HEAD identity.

## Artifact contract

- The JSONL manifest contains one row for every one of the 873 Git name-status entries, in diff order.
- Every current path records mode, Git blob ID, SHA-256, size, category, tracked state, likely worker/domain, central-baseline relation, exact review evidence, linked finding IDs, and required reconciliation actions.
- Every old path records its old-commit mode, Git blob ID, SHA-256, size, category, and likely prior worker/domain.
- `current_hash_rereview_required` is false only for deleted entries, exact-current-hash achieved evidence, or an `R100` rename with exact old-path evidence.
- The error fragment records the one bounded-output warning encountered; no command returned a nonzero exit status during this worker run.
