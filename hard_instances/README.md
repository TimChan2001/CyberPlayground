# CyberPlayground Hard Instances

Imported from `/Users/yiyang/bug-synthesis/hard/hardness-review-20260617-total1000/at-or-above-hardness-bar/bugs.json`.

This directory contains the reviewed hard static corpus:

- `bugs.json`: all 1000 accepted hard bug records in the rich static-manifest schema.
- `projects.json`: project metadata derived from pinned source revisions and build recipes.
- `by_project/`: full records split by project.
- `by_class/`: full records split by bug class.
- `clearly-hard-enough/`: 536 records.
- `borderline-hard/`: 464 records.
- `playground_compatible/`: 997 single-hunk records that match the current CyberPlayground single-diff runtime loader, plus `excluded_multi_hunk.json`.
- `review/`: review provenance and scratch-batch guardrail artifacts.
- `MANIFEST.json`: machine-readable counts and import notes.
- `build_recipe_tests/`: smoke-test runner, JSON results, and summary for the build recipes.

The current source review reports 1000 at-or-above-hardness-bar bugs, 0 below-bar bugs, and 0 scratch-batch hint-comment leaks.
Build recipes remain the same 40 project recipes smoke-tested on 2026-06-17; the latest smoke run passed all 40 projects.

Recipe and project metadata pin source identity explicitly: checkout-based sources use full git commit hashes, and archive-only sources use exact release tags or archive names. Branch-tip pseudo-references are not used.

## By Bug Class

| bug_class | count |
|---|---:|
| alloc | 153 |
| doublefree | 159 |
| intover | 56 |
| spatial | 403 |
| typeconf | 21 |
| uaf | 93 |
| uninit | 115 |

## By Project

| project | count |
|---|---:|
| cgltf | 11 |
| cjson | 33 |
| dr_flac | 6 |
| dr_mp3 | 4 |
| dr_wav | 8 |
| expat | 39 |
| ezxml | 11 |
| freetype | 49 |
| frozen | 14 |
| giflib | 14 |
| heatshrink | 6 |
| http_parser | 6 |
| inih | 3 |
| iniparser | 9 |
| jsmn | 5 |
| json-c | 43 |
| json_parser | 5 |
| lcms | 20 |
| libconfini | 6 |
| libcsv | 9 |
| libpng | 38 |
| libtiff | 59 |
| libucl | 36 |
| libxml2 | 125 |
| lua | 41 |
| lz4 | 40 |
| md4c | 32 |
| miniz | 13 |
| mjson | 6 |
| nanosvg | 13 |
| oniguruma | 45 |
| parson | 24 |
| pcre2 | 44 |
| slre | 4 |
| stb | 27 |
| tomlc99 | 15 |
| utf8proc | 5 |
| yyjson | 38 |
| zlib | 18 |
| zstd | 76 |
