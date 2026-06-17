#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/http_parser: https://github.com/nodejs/http-parser.git @ git_commit ec8b5ee63f0e51191ea43bb0c6eac7bfbff3141d
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ="$SLOT_DIR/http_parser.o"

clang $SAN -I"$SRC" -c "$SRC/http_parser.c" -o "$OBJ"
clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$OBJ" \
    -o "$OUT"
