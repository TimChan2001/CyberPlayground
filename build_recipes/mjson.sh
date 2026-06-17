#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/mjson: https://github.com/cesanta/mjson.git @ release_tag 1.2.7
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ="$SLOT_DIR/mjson.o"

clang $SAN -I"$SRC/src" -c "$SRC/src/mjson.c" -o "$OBJ"
clang $SAN \
    -I"$SRC/src" \
    "$HARNESS" "$MAIN_C" "$OBJ" \
    -lm -o "$OUT"
