#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/slre: https://github.com/cesanta/slre.git @ git_commit 9075c67cad47d62ba4a4f8f452ae46bb21124f7b
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ="$SLOT_DIR/slre.o"

clang $SAN -I"$SRC" -c "$SRC/slre.c" -o "$OBJ"
clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$OBJ" \
    -o "$OUT"
