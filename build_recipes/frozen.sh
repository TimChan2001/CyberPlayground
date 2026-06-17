#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/frozen: https://github.com/cesanta/frozen.git @ git_commit a42fc3365d7d4e96a5be146b88870dabc794bbc8
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ="$SLOT_DIR/frozen.o"

clang $SAN -I"$SRC" -c "$SRC/frozen.c" -o "$OBJ"
clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$OBJ" \
    -lm -o "$OUT"
