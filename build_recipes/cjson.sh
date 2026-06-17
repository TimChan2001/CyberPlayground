#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/cjson: https://github.com/DaveGamble/cJSON @ git_commit c859b25da02955fef659d658b8f324b5cde87be3
#   instances/cjson: https://github.com/DaveGamble/cJSON.git @ git_commit fb16e5cf358798aabb049655975cde8427101056
# Branch-tip source references are forbidden.
set -euo pipefail
cd "$SRC"
clang -fsanitize=address -g -O1 -c cJSON.c -o cJSON.o
clang -fsanitize=address -g -O1 -I . "$HARNESS" "$COMMON/main.c" cJSON.o -lm -o "$OUT"
