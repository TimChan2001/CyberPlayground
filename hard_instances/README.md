# CyberPlayground Hard Instances

Imported from `/Users/yiyang/bug-synthesis/hard/hardness-review-20260616/at-or-above-hardness-bar/bugs.json`.

This directory contains the reviewed hard static corpus:

- `bugs.json`: all 500 accepted hard bug records in the rich static-manifest schema.
- `projects.json`: project metadata derived from the records.
- `by_project/`: full records split by project.
- `by_class/`: full records split by bug class.
- `clearly-hard-enough/`: classification view; contains all 500 records.
- `borderline-hard/`: classification view; empty for this review.
- `playground_compatible/`: 497 single-hunk records that match the current CyberPlayground single-diff runtime loader, plus `excluded_multi_hunk.json` for the 3 preserved multi-hunk static records.
- `review/`: review provenance and hint-comment scan artifacts.
- `MANIFEST.json`: machine-readable counts and import notes.
- `build_recipe_tests/`: smoke-test runner, JSON results, and summary for the build recipes.

The source review reported 500 clearly-hard-enough bugs, 0 borderline-hard bugs,
0 below-bar bugs, and 0 injected hint-comment leaks. These are static candidates;
no PoCs or sanitizer validation logs are bundled here.

Build recipes are present for all 40 projects and were smoke-tested with the
CyberPlayground recipe contract (`SRC`, `OUT`, `SAN`, `HARNESS`, `COMMON`) on
2026-06-17. The latest smoke run passed all 40 projects; see
`build_recipe_tests/SUMMARY.md` and `build_recipe_tests/results.json`.

Recipe and project metadata pin source identity explicitly: checkout-based
sources use full git commit hashes, and archive-only sources use exact release
tags or archive names. Branch-tip pseudo-references are not used.
