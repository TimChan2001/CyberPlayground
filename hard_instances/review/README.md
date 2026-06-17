# Hardness Review 2026-06-16

Scope: active hard corpus after wiping below-bar static-retrieval candidates.

Inputs:

- Project manifests under `*-hard-20260615`.
- Project manifests under `*-hard-20260616`.
- Source-audit top-up manifest under `source-audit-more-20260616`.
- Wiped/disabled batches: `topup-hard-20260615` and `more-hard-20260616`.

Basis: static manifest review against the hard-natural rubric. No PoCs or project binaries were executed.

Verdicts:

- `clearly hard enough`: 500
- `borderline hard`: 0

Policy used:

- Per-project `llm_source_audit` records with specific named invariants and nonlocal path stories were classified as clearly hard enough.
- `llm_source_audit_with_static_retrieval` records are no longer accepted in this corpus; if present, this script fails before writing outputs.
- Records from retired below-bar batches, including `topup_20260615_hard_` and `more_20260616_hard_` ID prefixes, are rejected even if relabeled.

Hint-comment scan:

- Added/changed comment lines with explicit bug-hint wording: 0

## By Project

| project | clearly hard enough | borderline hard | total |
|---|---:|---:|---:|
| cgltf | 8 | 0 | 8 |
| cjson | 27 | 0 | 27 |
| dr_flac | 5 | 0 | 5 |
| dr_mp3 | 3 | 0 | 3 |
| dr_wav | 6 | 0 | 6 |
| expat | 28 | 0 | 28 |
| ezxml | 4 | 0 | 4 |
| freetype | 15 | 0 | 15 |
| frozen | 5 | 0 | 5 |
| giflib | 8 | 0 | 8 |
| heatshrink | 4 | 0 | 4 |
| http_parser | 6 | 0 | 6 |
| inih | 3 | 0 | 3 |
| iniparser | 6 | 0 | 6 |
| jsmn | 3 | 0 | 3 |
| json-c | 27 | 0 | 27 |
| json_parser | 4 | 0 | 4 |
| lcms | 11 | 0 | 11 |
| libconfini | 5 | 0 | 5 |
| libcsv | 4 | 0 | 4 |
| libpng | 12 | 0 | 12 |
| libtiff | 27 | 0 | 27 |
| libucl | 26 | 0 | 26 |
| libxml2 | 43 | 0 | 43 |
| lua | 33 | 0 | 33 |
| lz4 | 25 | 0 | 25 |
| md4c | 8 | 0 | 8 |
| miniz | 10 | 0 | 10 |
| mjson | 4 | 0 | 4 |
| nanosvg | 7 | 0 | 7 |
| oniguruma | 18 | 0 | 18 |
| parson | 11 | 0 | 11 |
| pcre2 | 21 | 0 | 21 |
| slre | 4 | 0 | 4 |
| stb | 10 | 0 | 10 |
| tomlc99 | 10 | 0 | 10 |
| utf8proc | 4 | 0 | 4 |
| yyjson | 12 | 0 | 12 |
| zlib | 13 | 0 | 13 |
| zstd | 20 | 0 | 20 |

## By Bug Class

| bug_class | clearly hard enough | borderline hard | total |
|---|---:|---:|---:|
| alloc | 90 | 0 | 90 |
| doublefree | 70 | 0 | 70 |
| intover | 27 | 0 | 27 |
| spatial | 168 | 0 | 168 |
| typeconf | 21 | 0 | 21 |
| uaf | 93 | 0 | 93 |
| uninit | 31 | 0 | 31 |

## By Source Batch

| source_batch | clearly hard enough | borderline hard | total |
|---|---:|---:|---:|
| project-hard-20260615 | 266 | 0 | 266 |
| project-hard-20260616 | 218 | 0 | 218 |
| source-audit-more-20260616 | 16 | 0 | 16 |

Artifacts:

- `hardness_review_20260616.json`: one review row per bug.
- `hardness_review_20260616.csv`: spreadsheet-friendly form.
- `clearly-hard-enough/bugs.json`: full bug records in the clear tier.
- `borderline-hard/bugs.json`: full bug records in the borderline tier.
- `hint_comment_scan_20260616.json`: data-leakage scan results for injected hint comments.
