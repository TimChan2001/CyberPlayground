#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/jsmn: https://github.com/zserge/jsmn.git @ git_commit 25647e692c7906b96ffd2b05ca54c097948e879c
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ="$SLOT_DIR/jsondump.o"

clang $SAN \
    -Dmain=jsmn_jsondump_main \
    -I"$SRC" \
    -c "$SRC/example/jsondump.c" -o "$OBJ"
clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$OBJ" \
    -o "$OUT"
