#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/utf8proc: https://github.com/JuliaStrings/utf8proc.git @ git_commit b3e0f28adaec943ac25e3e27514dd6037e7a022e
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ="$SLOT_DIR/utf8proc.o"

clang $SAN -I"$SRC" -c "$SRC/utf8proc.c" -o "$OBJ"
clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$OBJ" \
    -o "$OUT"
