#!/usr/bin/env bash
set -euo pipefail
cd "$SRC"
clang -fsanitize=address -g -O1 -c cJSON.c -o cJSON.o
clang -fsanitize=address -g -O1 -I . "$HARNESS" "$COMMON/main.c" cJSON.o -lm -o "$OUT"
