#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/ezxml: https://github.com/lxfontes/ezxml.git @ git_commit dcb17484da2591e42c739598729fe5bdf687cca6
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ="$SLOT_DIR/ezxml.o"

clang $SAN -I"$SRC" -c "$SRC/ezxml.c" -o "$OBJ"
clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$OBJ" \
    -o "$OUT"
