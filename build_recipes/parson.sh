#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/parson: https://github.com/kgabis/parson.git @ git_commit ba29f4eda9ea7703a9f6a9cf2b0532a2605723c3
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ="$SLOT_DIR/parson.o"

clang $SAN -I"$SRC" -c "$SRC/parson.c" -o "$OBJ"
clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$OBJ" \
    -o "$OUT"
