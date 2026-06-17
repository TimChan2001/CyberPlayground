#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/libcsv: https://github.com/rgamble/libcsv.git @ git_commit b1d5212831842ee5869d99bc208a21837e4037d5
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ="$SLOT_DIR/libcsv.o"

clang $SAN -I"$SRC" -c "$SRC/libcsv.c" -o "$OBJ"
clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$OBJ" \
    -o "$OUT"
